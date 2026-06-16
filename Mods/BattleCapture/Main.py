API_VERSION = 'API_v1.0'
MOD_NAME = 'BattleCapture'
MOD_VERSION = '1.6.0'

# BattleCapture mod
# Purpose: capture who died and when during a battle.
#
# Output:
#   BattleCapture.json (stable, overwritten as events occur)
#
# Data captured per death:
#   vehicleId, playerName, teamId, shipName (if known), subtype (if known),
#   killedAt (elapsed seconds from first capture trigger), ts (unix seconds)
#
# v1.5: aggressive roster reconciliation - backfill death records from roster on every write
# v1.5.1: log ship object attributes on first battle for discovery of shipId attr name
# v1.6.0: removed shipId collection (not reliably available via mod API)

try:
	import time
	import utils
	import events
	import battle
except:
	pass

try:
	MOD_PATH = utils.getModDir()
except:
	MOD_PATH = ''

_output_file = 'BattleCapture.json'
_battle_output_file = None

_started = False
_battle_start_ts = 0

_players = {}      # vid -> { vehicleId, playerName, teamId, shipName, subtype }
_dead_seen = {}    # vid -> True
_deaths = []       # ordered death events
_events = []       # ordered lifecycle events for diagnostics
_lifecycle = {
	'battleShownTs': None,
	'quitTs': None,
	'endTs': None,
}


def _log(msg):
	try:
		utils.logInfo('[BattleCapture] ' + str(msg))
	except:
		pass


def _json_encode(obj):
	try:
		return utils.jsonEncode(obj)
	except:
		try:
			import json
			return json.dumps(obj, indent=2)
		except:
			return str(obj)


def _safe(v):
	if v is None:
		return None
	if isinstance(v, (bool, int, float)):
		return v
	try:
		if isinstance(v, long):
			return int(v)
	except:
		pass
	try:
		if isinstance(v, unicode):
			return v
	except:
		pass
	try:
		if isinstance(v, bytes):
			return v.decode('utf-8', 'ignore')
	except:
		pass
	return str(v)


def _get_attr(obj, name, default=None):
	try:
		return getattr(obj, name, default)
	except:
		return default


def _elapsed():
	if not _battle_start_ts:
		return 0
	try:
		return int(time.time()) - _battle_start_ts
	except:
		return 0


def _append_event(event_name, details=None):
	try:
		ev = {
			'event': _safe(event_name),
			'ts': int(time.time()),
			'elapsed': _elapsed(),
			'deathCount': len(_deaths),
		}
		if details is not None:
			ev['details'] = details
		_events.append(ev)
		# Keep log bounded in long sessions.
		if len(_events) > 500:
			del _events[0]
	except:
		pass


def _ensure_started(trigger_name):
	global _started, _battle_start_ts, _battle_output_file
	if _started:
		return
	try:
		_battle_start_ts = int(time.time())
	except:
		_battle_start_ts = 0
	if not _battle_start_ts:
		try:
			_battle_start_ts = int(time.time())
		except:
			_battle_start_ts = 0
	_battle_output_file = 'BattleCapture_%s.json' % str(_battle_start_ts)
	_started = True
	_append_event('captureStarted', {'trigger': _safe(trigger_name), 'battleFile': _battle_output_file})
	_log('Capture started from ' + str(trigger_name))


def _extract_vehicle_id(pinfo):
	for attr in ('shipId', 'vehicleId', 'shipID', 'vehicleID'):
		v = _get_attr(pinfo, attr)
		if v is not None:
			try:
				return int(v)
			except:
				pass
	return None


def _extract_player_name(pinfo):
	for attr in ('name', 'playerName', 'nickName', 'nickname'):
		v = _get_attr(pinfo, attr)
		if v:
			return _safe(v)
	return None


# Removed _extract_ship_id - shipId not reliably available via mod API



def _extract_vehicle_id_from_ship(ship):
	"""Try all known attribute names for the per-battle vehicle instance ID."""
	# Python name-mangling: _Ship__id is the mangled form of __id on Ship class
	for attr in ('_Ship__id', 'vehicleId', 'shipId', 'vehicleID', 'shipID', 'id'):
		try:
			v = getattr(ship, attr, None)
			if v is not None:
				return int(v)
		except:
			pass
	return None


_ship_attrs_logged = False


def _log_ship_attrs(ship):
	"""One-time dump of all attributes on the first ship object for discovery."""
	global _ship_attrs_logged
	if _ship_attrs_logged:
		return
	_ship_attrs_logged = True
	try:
		attrs = {}
		for k in dir(ship):
			if k.startswith('__'):
				continue
			try:
				v = getattr(ship, k, None)
				if callable(v):
					continue
				attrs[k] = _safe(v)
			except:
				pass
		_log('SHIP_ATTRS: ' + str(attrs))
	except:
		pass


def _refresh_ship_info_from_all_ships():
	"""Best effort: fill ship name/subtype/shipId when visible via getAllShips()."""
	try:
		all_ships = battle.getAllShips()
		if all_ships is None:
			return
		for ship in all_ships:
			try:
				_log_ship_attrs(ship)
				vid = _extract_vehicle_id_from_ship(ship)
				if vid is None:
					continue
				ship_id = _extract_ship_id(ship)
				ship_name = _safe(_get_attr(ship, 'name'))
				subtype = _safe(_get_attr(ship, 'subtype'))
				player_name = _safe(_get_attr(ship, 'playerName'))
				team_id = _safe(_get_attr(ship, 'teamId'))

				if vid not in _players:
					_players[vid] = {
						'vehicleId': vid,
						'playerName': player_name,
						'teamId': team_id,
						'shipName': ship_name,
						'subtype': subtype,
						'shipId': ship_id,
					}
				else:
					row = _players[vid]
					# Only fill in missing fields; never overwrite with None
					if not row.get('shipName') and ship_name:
						row['shipName'] = ship_name
					if not row.get('subtype') and subtype:
						row['subtype'] = subtype
					if not row.get('playerName') and player_name:
						row['playerName'] = player_name
					if not row.get('teamId') and team_id is not None:
						row['teamId'] = team_id
					if not row.get('shipId') and ship_id:
						row['shipId'] = ship_id
			except:
				pass
	except:
		pass


def _scan_players_for_deaths():
	"""Update roster and append new death events for newly dead players."""
	try:
		players_info = battle.getPlayersInfo()
		if not players_info:
			return

		_refresh_ship_info_from_all_ships()

		now = int(time.time())
		elapsed = _elapsed()

		for _pid, pinfo in players_info.items():
			try:
				vid = _extract_vehicle_id(pinfo)
				if vid is None:
					continue

				pname = _extract_player_name(pinfo)
				team_id = _safe(_get_attr(pinfo, 'teamId'))
				is_alive = _get_attr(pinfo, 'isAlive', True)

				if vid not in _players:
					_players[vid] = {
						'vehicleId': vid,
						'playerName': pname,
						'teamId': team_id,
						'shipName': None,
						'subtype': None,
					}
				else:
					row = _players[vid]
					if row.get('playerName') is None and pname is not None:
						row['playerName'] = pname
					if row.get('teamId') is None and team_id is not None:
						row['teamId'] = team_id

				if (not is_alive) and (vid not in _dead_seen):
					_dead_seen[vid] = True
					row = _players.get(vid, {})
					ev = {
						'vehicleId': vid,
						'playerName': row.get('playerName'),
						'teamId': row.get('teamId'),
						'shipName': row.get('shipName'),
						'subtype': row.get('subtype'),
						'killedAt': elapsed,
						'ts': now,
					}
					_deaths.append(ev)
					_append_event('deathDetected', {
						'vehicleId': vid,
						'playerName': row.get('playerName'),
						'teamId': row.get('teamId')
					})
					_log('Death: player=%s vid=%s elapsed=%ds' % (
						str(ev.get('playerName')), str(vid), elapsed))
			except:
				pass
	except:
		pass


def _reconcile_deaths():
	"""Backfill any missing ship metadata in recorded death events from the current roster."""
	try:
		for ev in _deaths:
			vid = ev.get('vehicleId')
			if vid is None:
				continue
			row = _players.get(vid)
			if row is None:
				continue
			if not ev.get('shipName') and row.get('shipName'):
				ev['shipName'] = row['shipName']
			if not ev.get('subtype') and row.get('subtype'):
				ev['subtype'] = row['subtype']
			# shipId removed - not reliably available via mod API
			if not ev.get('playerName') and row.get('playerName'):
				ev['playerName'] = row['playerName']
			if not ev.get('teamId') and row.get('teamId') is not None:
				ev['teamId'] = row['teamId']
	except:
		pass


def _write_text(path, text):
	try:
		f = open(path, 'wb')
		f.write(text)
		f.close()
	except:
		pass


def _get_end_reason():
	try:
		q = _lifecycle.get('quitTs')
		e = _lifecycle.get('endTs')
		if q and e:
			if q >= e:
				return 'quit'
			return 'end'
		if q:
			return 'quit'
		if e:
			return 'end'
	except:
		pass
	return None


def _write_output(trigger_name):
	try:
		data = {
			'mod': MOD_NAME,
			'version': MOD_VERSION,
			'ts': int(time.time()),
			'started': _started,
			'battleStartTs': _battle_start_ts,
			'battleFile': _battle_output_file,
			'lifecycle': {
				'battleShownTs': _lifecycle.get('battleShownTs'),
				'quitTs': _lifecycle.get('quitTs'),
				'endTs': _lifecycle.get('endTs'),
				'endReason': _get_end_reason(),
			},
			'elapsed_seconds': _elapsed(),
			'trigger': trigger_name,
			'deathCount': len(_deaths),
			'eventCount': len(_events),
			'lineup': list(_players.values()),
			'events': list(_events),
			'deaths': list(_deaths),
		}
		text = _json_encode(data)
		try:
			if isinstance(text, unicode):
				text = text.encode('utf-8', 'ignore')
		except:
			pass
		try:
			if isinstance(text, str):
				text = text.encode('utf-8', 'ignore')
		except:
			pass

		# Stable latest file (for quick inspection)
		stable_path = MOD_PATH + '/' + _output_file
		_write_text(stable_path, text)

		# Per-battle timestamped file (prevents overwriting prior battle capture)
		if _battle_output_file:
			battle_path = MOD_PATH + '/' + _battle_output_file
			_write_text(battle_path, text)
	except:
		pass


def _reset_state():
	global _started, _battle_start_ts, _battle_output_file, _players, _dead_seen, _deaths, _events
	_started = False
	_battle_start_ts = 0
	_battle_output_file = None
	_players = {}
	_dead_seen = {}
	_deaths = []
	_events = []
	_lifecycle['battleShownTs'] = None
	_lifecycle['quitTs'] = None
	_lifecycle['endTs'] = None


def _start_or_update(trigger_name):
	_append_event(trigger_name)
	_ensure_started(trigger_name)
	_scan_players_for_deaths()
	_reconcile_deaths()
	_write_output(trigger_name)


def _on_battle_shown(*args, **kwargs):
	_lifecycle['battleShownTs'] = int(time.time())
	_start_or_update('onBattleShown')


def _on_players_list_updated(*args, **kwargs):
	_start_or_update('onPlayersListUpdated')


def _on_battle_end(*args, **kwargs):
	_lifecycle['endTs'] = int(time.time())
	_append_event('onBattleEnd')
	if _started:
		_refresh_ship_info_from_all_ships()
		_scan_players_for_deaths()
		_reconcile_deaths()
		_write_output('onBattleEnd')
		_log('Battle ended: deathCount=%d' % len(_deaths))
	_reset_state()


def _on_battle_quit(*args, **kwargs):
	_lifecycle['quitTs'] = int(time.time())
	_append_event('onBattleQuit')
	if _started:
		_refresh_ship_info_from_all_ships()
		_scan_players_for_deaths()
		_reconcile_deaths()
		_write_output('onBattleQuit')
	_reset_state()


_log('BattleCapture v%s loaded' % MOD_VERSION)

try:
	events.onBattleShown(_on_battle_shown)
except:
	_log('ERR: onBattleShown')

try:
	events.onPlayersListUpdated(_on_players_list_updated)
except:
	_log('ERR: onPlayersListUpdated')

try:
	events.onBattleEnd(_on_battle_end)
except:
	_log('ERR: onBattleEnd')

try:
	events.onBattleQuit(_on_battle_quit)
except:
	_log('ERR: onBattleQuit')
