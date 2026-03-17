API_VERSION = 'API_v1.0'
MOD_NAME = 'BattleResults'


try:
	import time
	import utils
	import events
except:
	pass

try:
	MOD_PATH = utils.getModDir()
except:
	MOD_PATH = ''


JsonFileName = 'BattleResults.json'

_ship_data = None

_battles = {}

def _get_arena_id_from_result(battle_result):
	try:
		common = _try_get(battle_result, 'common', {})
		return _try_get(common, 'arena_id', None)
	except:
		return None


def _get_battle_state(arena_id):
	try:
		if arena_id is None:
			return None
		st = _battles.get(arena_id)
		if st is None:
			st = {
				'arena_id': arena_id,
				'file_path': None,
				'ship_data': None,
			}
			_battles[arena_id] = st
		return st
	except:
		return None


def _choose_battle_file_path(arena_id, ts):
	try:
		try:
			suffix = time.strftime('%Y%m%d_%H%M%S', time.localtime(ts))
		except:
			suffix = str(ts)
		return MOD_PATH + '/BattleResults_' + suffix + '_arena_' + str(arena_id) + '.json'
	except:
		return MOD_PATH + '/BattleResults_' + str(ts) + '.json'

def _json_encode(obj):
	try:
		return utils.jsonEncode(obj)
	except:
		try:
			import json
			return json.dumps(obj)
		except:
			return str(obj)


def _safe_obj(obj, depth=2):
	try:
		if depth <= 0:
			return str(obj)
		if obj is None:
			return None
		if isinstance(obj, (int, long, float, bool)):
			return obj
		try:
			if isinstance(obj, unicode):
				return obj
		except:
			pass
		try:
			if isinstance(obj, bytes):
				try:
					return obj.decode('utf-8', 'ignore')
				except:
					return str(obj)
		except:
			pass
		if isinstance(obj, (list, tuple)):
			return [_safe_obj(x, depth - 1) for x in obj]
		if isinstance(obj, dict):
			out = {}
			for k in obj:
				out[str(k)] = _safe_obj(obj.get(k), depth - 1)
			return out
		try:
			return _safe_obj(vars(obj), depth - 1)
		except:
			return str(obj)
	except:
		return str(obj)


def _write_json_file_path(path, data):
	try:
		text = _json_encode(data)
		try:
			if isinstance(text, unicode):
				text = text.encode('utf-8', 'ignore')
		except:
			pass
		try:
			if isinstance(text, str):
				try:
					text = text.encode('utf-8', 'ignore')
				except:
					pass
		except:
			pass
		f = open(path, 'wb')
		f.write(text)
		f.close()
	except:
		pass

def _try_get(obj, key, default=0):
	try:
		if obj is None:
			return default
		try:
			v = obj.get(key)
			if v is None:
				return default
			return v
		except:
			pass
		try:
			return obj[key]
		except:
			return default
	except:
		return default


def _as_int(v, default=0):
	try:
		if v is None:
			return default
		if v is True:
			return 1
		if v is False:
			return 0
		try:
			return int(v)
		except:
			return default
	except:
		return default

def _on_battle_stats_received(battle_result):
	try:
		ts = int(time.time())
	except:
		ts = 0

	arena_id = _get_arena_id_from_result(battle_result)
	st = _get_battle_state(arena_id)

	me = _try_get(battle_result, 'me', {})
	common = _try_get(battle_result, 'common', {})
	privateData = _try_get(battle_result, 'privateData', {})
	try:
		ship_id = _try_get(me, 'vehicle_type_id', None)
		_ship_data = {
			'ship_id': _safe_obj(ship_id, 1),
		}
		if st:
			st['ship_data'] = _ship_data
	except:
		pass
	try:
		pass
	except:
		pass
	try:
		# Do not persist interactions (privacy + size)
		if isinstance(me, dict) and ('interactions' in me):
			me = dict(me)
			try:
				del me['interactions']
			except:
				pass
	except:
		pass

	try:
		if st:
			try:
				if st.get('file_path') is None:
					st['file_path'] = _choose_battle_file_path(arena_id, ts)
			except:
				pass
			out = {
				'ts': ts,
				'arena_id': arena_id,
                'ship': _safe_obj(st.get('ship_data'), 2),
				'me': _safe_obj(me, 3),
				'common': _safe_obj(common, 3),
				'privateData': _safe_obj(privateData, 3),
			}
			_write_json_file_path(st.get('file_path'), out)
	except:
		pass


try:
	events.onBattleStatsReceived(_on_battle_stats_received)
except:
	pass

