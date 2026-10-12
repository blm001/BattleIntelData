API_VERSION = 'API_v1.0'
MOD_NAME = 'BattleStart'
MOD_VERSION = '5.1'

# BattleStart Mod v5.1 for WoWsBattleIntel
# Captures per-player computed ship parameters at battle start.
# v5.1 changes:
#   - Full parameter parser for ALL consumable attributes (not just first)
#   - Retry mechanism for Random battles (event fires before data ready)
#   - onBattleEnd flag reset for multi-battle support
#   - Complete consumable data for both teams (not just allies)
# Data sources: dataHub 'shipBattleInfo' for all ship data (TTX, consumables, identity)
#               battle.getPlayersInfo() for supplemental player info
# Output: BattleStart.json in mod folder (stable) + timestamped backup.

try:
    import time
    import utils
    import events
    import dataHub
    import constants
    import battle
except:
    pass

try:
    MOD_PATH = utils.getModDir()
except:
    MOD_PATH = ''

CC = None
try:
    CC = constants.UiComponents
except:
    pass

# Global state for capture retry mechanism
_captured_once = False  # Flag to prevent multiple captures per battle
_capture_timestamps = {}  # Track timing of operations


def _log(msg):
    try:
        utils.logInfo('[BattleStart] ' + str(msg))
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


def _safe_val(v):
    """Convert a value to a JSON-safe type."""
    if v is None:
        return None
    if isinstance(v, (int, float, bool)):
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
    """Safely get an attribute from an object."""
    try:
        return getattr(obj, name, default)
    except:
        return default


def _get_ttx_value(ttx, *path):
    """Navigate a TTX object path and return .value if present."""
    try:
        current = ttx
        for p in path:
            if current is None:
                return None
            current = _get_attr(current, p)
        if current is None:
            return None
        return _get_attr(current, 'value')
    except:
        return None


def _add_timestamp(event_name):
    """Add timestamp for tracking when events occur."""
    global _capture_timestamps
    try:
        now = int(time.time())
        _capture_timestamps[event_name] = now
    except:
        pass


def _parse_all_consumable_params(consumable_obj):
    """
    Parse ALL items in activeAttributes.neutral list into structured dictionary.
    Returns dict mapping parameter names to values (e.g., {'distShip': 5.0, 'distTorpedo': 3.5}).
    Based on ConsumableProbe v5.1 full parameter parser.
    """
    try:
        active_attrs = _get_attr(consumable_obj, 'activeAttributes')
        if active_attrs is None:
            return None

        neutral = _get_attr(active_attrs, 'neutral')
        if neutral is None or not hasattr(neutral, '__len__') or len(neutral) == 0:
            return None

        parsed_params = {}

        for idx, item in enumerate(neutral):
            try:
                param_name = None
                param_value = None

                # Extract paramName and measuredValue from each item
                for attr_name in ['paramName', 'measuredValue']:
                    try:
                        attr_val = _get_attr(item, attr_name)
                        if attr_val is not None:
                            if attr_name == 'paramName':
                                param_name = str(attr_val)
                            elif attr_name == 'measuredValue':
                                # Try to convert to number if possible
                                try:
                                    param_value = float(attr_val)
                                except:
                                    param_value = str(attr_val)
                    except:
                        pass

                # Add to parsed_params if we got both name and value
                if param_name and param_value is not None:
                    parsed_params[param_name] = param_value

            except:
                pass

        if parsed_params:
            return parsed_params

        return None

    except:
        return None


def _extract_consumables(ship):
    """
    Extract consumable data from shipBattleInfo entity using v5.1 full parameter parser.
    Returns dict with mainConsumables (array) and altConsumables (array of choice objects).
    Based on ConsumableProbe v5.1 proven approach.
    """
    result = {
        'mainConsumables': [],
        'altConsumables': []
    }

    def _process_consumable(cons, slot_idx):
        """Process a single consumable object and return structured data."""
        try:
            cons_data = {
                'slot': slot_idx,
                'title': _safe_val(_get_attr(cons, 'title')),
                'description': _safe_val(_get_attr(cons, 'description')),
                'iconPath': _safe_val(_get_attr(cons, 'iconPath')),
                'iconName': _safe_val(_get_attr(cons, 'iconName')),
            }

            # Get raw activeAttributes.neutral strings
            try:
                active_attrs = _get_attr(cons, 'activeAttributes')
                if active_attrs:
                    neutral = _get_attr(active_attrs, 'neutral')
                    if neutral and hasattr(neutral, '__len__') and len(neutral) > 0:
                        # Store raw strings for debugging
                        cons_data['activeAttributes_neutral'] = [str(item) for item in neutral]
                    else:
                        cons_data['activeAttributes_neutral'] = []
                else:
                    cons_data['activeAttributes_neutral'] = []
            except:
                cons_data['activeAttributes_neutral'] = []

            # Parse all parameters using v5.1 parser
            parsed = _parse_all_consumable_params(cons)
            cons_data['activeAttributes_neutral_parsed'] = parsed

            return cons_data

        except:
            return None

    # Process mainConsumables (the player's equipped consumables)
    try:
        main_cons = _get_attr(ship, 'mainConsumables') or []

        for slot_idx, cons in enumerate(main_cons):
            cons_data = _process_consumable(cons, slot_idx)
            if cons_data:
                result['mainConsumables'].append(cons_data)

    except:
        pass

    # Process altConsumables
    # Structure: List of lists, each inner list is alternatives for one slot
    try:
        alt_cons = _get_attr(ship, 'altConsumables') or []
        if hasattr(alt_cons, '__len__') and len(alt_cons) > 0:

            for alt_slot_idx, alt_choices in enumerate(alt_cons):
                if not hasattr(alt_choices, '__len__'):
                    continue

                alt_slot_data = {
                    'mainSlot': alt_slot_idx,
                    'choices': []
                }

                for choice_idx, cons in enumerate(alt_choices):
                    cons_data = _process_consumable(cons, alt_slot_idx)
                    if cons_data:
                        cons_data['choiceIndex'] = choice_idx
                        # Remove 'slot' since it's redundant with mainSlot
                        cons_data.pop('slot', None)
                        alt_slot_data['choices'].append(cons_data)

                if alt_slot_data['choices']:
                    result['altConsumables'].append(alt_slot_data)

    except:
        pass

    return result


def _extract_torpedo_ammo(torp_ammo, prefix=''):
    """Extract torpedo ammo stats (range, damage, speed, visibility, canHitClasses)."""
    if torp_ammo is None:
        return {}
    result = {}
    p = prefix
    result[p + 'torpedoRange'] = _safe_val(_get_ttx_value(torp_ammo, 'maxDist'))
    result[p + 'torpedoDamage'] = _safe_val(_get_ttx_value(torp_ammo, 'damage'))
    result[p + 'torpedoSpeed'] = _safe_val(_get_ttx_value(torp_ammo, 'speed'))
    result[p + 'torpedoVisibility'] = _safe_val(_get_ttx_value(torp_ammo, 'visibility'))
    # Which ship classes this torpedo can hit (e.g., deepwater targeting)
    try:
        hit_classes = _get_attr(torp_ammo, 'canHitClasses')
        if hit_classes:
            result[p + 'torpedoCanHitClasses'] = list(hit_classes)
    except:
        pass
    return {k: v for k, v in result.iteritems() if v is not None}


def _extract_ship_ttx(ship):
    """
    Extract computed ship parameters from shipBattleInfo.shipTTX.
    Returns dict with visibility, artillery, torpedoes, mobility, etc.
    """
    ttx = _get_attr(ship, 'shipTTX')
    if ttx is None:
        return None
    result = {}
    try:
        # Visibility
        vis = _get_attr(ttx, 'visibility')
        if vis:
            result['concealmentByShip'] = _safe_val(_get_ttx_value(vis, 'visibilityByShip', 'normal'))
            result['concealmentByAir'] = _safe_val(_get_ttx_value(vis, 'visibilityByPlane', 'normal'))
            result['concealmentInSmoke'] = _safe_val(_get_ttx_value(vis, 'visibilityByShip', 'smoke'))

        # Artillery
        art = _get_attr(ttx, 'artillery')
        if art:
            result['mainGunRange'] = _safe_val(_get_ttx_value(art, 'mgMaxDist'))
            result['mainGunReload'] = _safe_val(_get_ttx_value(art, 'mgReloadTime'))
            result['secondaryRange'] = _safe_val(_get_ttx_value(art, 'atbaMaxDist'))

            # Main gun info (caliber, barrel count, turret layout)
            # Secondary battery per-group details
            atba = _get_attr(art, 'atba')
            if atba and len(atba) > 0:
                try:
                    atba_groups = []
                    for atba_gun in atba:
                        group = {}
                        ng = _get_ttx_value(atba_gun, 'numGuns')
                        nb = _get_ttx_value(atba_gun, 'numBarrels')
                        rt = _get_ttx_value(atba_gun, 'reloadTime')
                        if ng is not None:
                            group['numGuns'] = int(ng)
                        if nb is not None:
                            group['numBarrels'] = int(nb)
                        if rt is not None:
                            group['reloadTime'] = _safe_val(rt)
                        # Ammo damage from first ammo in ammoList
                        ammo_list = _get_attr(atba_gun, 'ammoList')
                        if ammo_list and len(ammo_list) > 0:
                            dmg = _get_ttx_value(ammo_list[0], 'damage')
                            if dmg is not None:
                                group['ammoDamage'] = _safe_val(dmg)
                        if group:
                            atba_groups.append(group)
                    if atba_groups:
                        result['secondaryGroups'] = atba_groups
                except:
                    pass

            # Main gun info
            main_guns = _get_attr(art, 'mainGun')
            if main_guns and len(main_guns) > 0:
                first_gun = main_guns[0]
                result['caliber'] = _safe_val(_get_ttx_value(first_gun, 'caliber'))
                # Calculate total barrels and capture per-turret layout
                try:
                    total_barrels = 0
                    turret_layout = []
                    for gun in main_guns:
                        num_guns = _get_ttx_value(gun, 'numGuns') or 0
                        num_barrels = _get_ttx_value(gun, 'numBarrels') or 0
                        total_barrels += num_guns * num_barrels
                        if num_guns > 0 and num_barrels > 0:
                            turret_layout.append({'numGuns': int(num_guns), 'numBarrels': int(num_barrels)})
                    if total_barrels > 0:
                        result['totalBarrels'] = total_barrels
                    if turret_layout:
                        result['mainGunTurretLayout'] = turret_layout
                except:
                    pass

            # Burst fire mode
            alt_fire = _get_attr(art, 'altFireMode')
            if alt_fire:
                result['burstFireShots'] = _safe_val(_get_ttx_value(alt_fire, 'numShots'))
                result['burstFireReload'] = _safe_val(_get_ttx_value(alt_fire, 'reloadTime'))

            # HE ammo stats
            ammo_he = _get_attr(art, 'ammoHE')
            if ammo_he:
                result['heFireChance'] = _safe_val(_get_ttx_value(ammo_he, 'fireChance'))
                result['heDamage'] = _safe_val(_get_ttx_value(ammo_he, 'damage'))
                result['hePenetration'] = _safe_val(_get_ttx_value(ammo_he, 'piercing'))

            # SAP/CS ammo stats
            ammo_cs = _get_attr(art, 'ammoCS')
            if ammo_cs:
                result['sapDamage'] = _safe_val(_get_ttx_value(ammo_cs, 'damage'))
                result['sapPenetration'] = _safe_val(_get_ttx_value(ammo_cs, 'piercing'))

            # AP ammo stats
            ammo_ap = _get_attr(art, 'ammoAP')
            if ammo_ap:
                result['apDamage'] = _safe_val(_get_ttx_value(ammo_ap, 'damage'))
                result['apPenetration'] = _safe_val(_get_ttx_value(ammo_ap, 'piercing'))

        # Torpedoes (surface ships)
        torps = _get_attr(ttx, 'torpedoes')
        if torps:
            result['torpedoReload'] = _safe_val(_get_ttx_value(torps, 'reloadTime'))

            # Torpedo launcher layout
            launchers = _get_attr(torps, 'launchers')
            if launchers and len(launchers) > 0:
                try:
                    launcher_layout = []
                    for launcher in launchers:
                        ng = _get_ttx_value(launcher, 'numGuns')
                        nb = _get_ttx_value(launcher, 'numBarrels')
                        if ng is not None and nb is not None:
                            launcher_layout.append({'numGuns': int(ng), 'numBarrels': int(nb)})
                    if launcher_layout:
                        result['torpedoLauncherLayout'] = launcher_layout
                except:
                    pass

            # Normal torpedoes
            torp = _get_attr(torps, 'torpedo')
            if torp:
                result.update(_extract_torpedo_ammo(torp))

            # Deepwater torpedoes
            torp_dw = _get_attr(torps, 'torpedoDeepwater')
            if torp_dw:
                result.update(_extract_torpedo_ammo(torp_dw, 'dw'))

            # Alt torpedoes (some ships have alternative torp options)
            torp_alt = _get_attr(torps, 'torpedoAlt')
            if torp_alt:
                result.update(_extract_torpedo_ammo(torp_alt, 'alt'))

        # Submarine torpedoes
        torp_groups = _get_attr(ttx, 'torpedoGroups')
        if torp_groups:
            sub_torp = _get_attr(torp_groups, 'torpedo')
            if sub_torp:
                result.update(_extract_torpedo_ammo(sub_torp, 'sub'))
            # Bow/stern reload
            bow_group = _get_attr(torp_groups, 'bowGroup')
            if bow_group:
                result['subBowReload'] = _safe_val(_get_ttx_value(bow_group, 'reloadTime'))
                result['subBowLoaders'] = _safe_val(_get_ttx_value(bow_group, 'numLoaders'))
            stern_group = _get_attr(torp_groups, 'sternGroup')
            if stern_group:
                result['subSternReload'] = _safe_val(_get_ttx_value(stern_group, 'reloadTime'))
                result['subSternLoaders'] = _safe_val(_get_ttx_value(stern_group, 'numLoaders'))

            # Sub alternate torpedoes
            sub_torp_alt = _get_attr(torp_groups, 'torpedoAlt')
            if sub_torp_alt:
                result.update(_extract_torpedo_ammo(sub_torp_alt, 'subAlt'))

            # Sub deepwater torpedoes
            sub_torp_dw = _get_attr(torp_groups, 'torpedoDeepwater')
            if sub_torp_dw:
                result.update(_extract_torpedo_ammo(sub_torp_dw, 'subDw'))

        # Mobility
        mob = _get_attr(ttx, 'mobility')
        if mob:
            result['speed'] = _safe_val(_get_ttx_value(mob, 'speed'))
            result['turningRadius'] = _safe_val(_get_ttx_value(mob, 'turningRadius'))
            result['rudderTime'] = _safe_val(_get_ttx_value(mob, 'rudderTime'))
        uw_mob = _get_attr(ttx, 'underwaterMobility')
        if uw_mob:
            result['underwaterSpeed'] = _safe_val(_get_ttx_value(uw_mob, 'speed'))

        # Battery (submarines)
        battery = _get_attr(ttx, 'battery')
        if battery:
            result['batteryCapacity'] = _safe_val(_get_ttx_value(battery, 'capacity'))
            result['batteryRegenRate'] = _safe_val(_get_ttx_value(battery, 'regeneration'))

        # Air Defense
        aa = _get_attr(ttx, 'airDefense')
        if aa:
            avg_aura = _get_attr(aa, 'averageAura')
            if avg_aura:
                result['aaRange'] = _safe_val(_get_ttx_value(avg_aura, 'maxDist'))
            result['aaRating'] = _safe_val(_get_ttx_value(aa, 'integralValue'))
            # Flak burst count
            bubble = _get_attr(aa, 'bubble')
            if bubble:
                result['aaFlakBursts'] = _safe_val(_get_ttx_value(bubble, 'numBubbles'))

        # Air Support
        air_sup = _get_attr(ttx, 'airSupport')
        if air_sup:
            result['airSupportRange'] = _safe_val(_get_ttx_value(air_sup, 'maxDist'))
            result['airSupportReload'] = _safe_val(_get_ttx_value(air_sup, 'reloadTime'))

            # HE bombers
            bomber_he = _get_attr(air_sup, 'bomberHE')
            if bomber_he:
                result['airSupportHESquadrons'] = _safe_val(_get_ttx_value(bomber_he, 'chargesNum'))
                bomb_he = _get_attr(bomber_he, 'bombHE')
                if bomb_he:
                    result['airSupportHEDamage'] = _safe_val(_get_ttx_value(bomb_he, 'damage'))
                    result['airSupportHEPenetration'] = _safe_val(_get_ttx_value(bomb_he, 'piercing'))
                    result['airSupportHEBurnChance'] = _safe_val(_get_ttx_value(bomb_he, 'burnChance'))
                    result['airSupportHENumBombs'] = _safe_val(_get_ttx_value(bomb_he, 'numBombs'))

            # AP bombers
            bomber_ap = _get_attr(air_sup, 'bomberAP')
            if bomber_ap:
                result['airSupportAPSquadrons'] = _safe_val(_get_ttx_value(bomber_ap, 'chargesNum'))
                bomb_ap = _get_attr(bomber_ap, 'bombAP')
                if bomb_ap:
                    result['airSupportAPDamage'] = _safe_val(_get_ttx_value(bomb_ap, 'damage'))
                    result['airSupportAPPenetration'] = _safe_val(_get_ttx_value(bomb_ap, 'piercing'))
                    result['airSupportAPNumBombs'] = _safe_val(_get_ttx_value(bomb_ap, 'numBombs'))

            # Depth charge bombers (ASW airstrike)
            bomber_dc = _get_attr(air_sup, 'bomberDC')
            if bomber_dc:
                result['airSupportDCSquadrons'] = _safe_val(_get_ttx_value(bomber_dc, 'chargesNum'))
                bomb_dc = _get_attr(bomber_dc, 'bombDC')
                if bomb_dc:
                    result['airSupportDCDamage'] = _safe_val(_get_ttx_value(bomb_dc, 'damage'))
                    result['airSupportDCBurnChance'] = _safe_val(_get_ttx_value(bomb_dc, 'burnChance'))
                    result['airSupportDCNumBombs'] = _safe_val(_get_ttx_value(bomb_dc, 'numBombs'))

        # Depth Charges (for ASW ships)
        dc = _get_attr(ttx, 'depthCharges')
        if dc:
            result['depthChargeRange'] = _safe_val(_get_ttx_value(dc, 'maxDist'))
            result['depthChargeDamage'] = _safe_val(_get_ttx_value(dc, 'damage'))
            result['depthChargeReload'] = _safe_val(_get_ttx_value(dc, 'reloadTime'))
            result['depthChargeMaxPacks'] = _safe_val(_get_ttx_value(dc, 'numCharges'))
            result['depthChargeBombsPerPack'] = _safe_val(_get_ttx_value(dc, 'numBombs'))

        # Durability
        dur = _get_attr(ttx, 'durability')
        if dur:
            result['maxHealth'] = _safe_val(_get_ttx_value(dur, 'health'))
            result['torpedoProtection'] = _safe_val(_get_ttx_value(dur, 'ptz'))

        # Armor
        armor = _get_attr(ttx, 'armor')
        if armor:
            result['armorMax'] = _safe_val(_get_ttx_value(armor, 'max'))
            result['armorMin'] = _safe_val(_get_ttx_value(armor, 'min'))

        # Pinger (submarines)
        pinger = _get_attr(ttx, 'pinger')
        if pinger:
            result['pingerRange'] = _safe_val(_get_ttx_value(pinger, 'maxDist'))
            result['pingerSpeed'] = _safe_val(_get_ttx_value(pinger, 'speed'))
            result['pingerReload'] = _safe_val(_get_ttx_value(pinger, 'reloadTime'))
    except:
        pass

    # Filter out None values
    return {k: v for k, v in result.iteritems() if v is not None} if result else None



def _extract_avatar_info(avatar):
    """Extract basic info from avatar component."""
    try:
        ship_ref = _get_attr(_get_attr(avatar, 'ship'), 'ref')
        ship_entity = _get_attr(ship_ref, 'ship') if ship_ref else None
        return {
            'playerId': _safe_val(_get_attr(avatar, 'id')),
            'playerName': _safe_val(_get_attr(avatar, 'name')),
            'teamId': _safe_val(_get_attr(avatar, 'teamId')),
            'isBot': _safe_val(_get_attr(avatar, 'isBot')),
            'shipId': _safe_val(_get_attr(ship_entity, 'id')) if ship_entity else None,
        }
    except:
        return None


def _extract_division_info(entity):
    """
    Extract division info from an entity's divisionMember component.
    Returns dict with division number and related flags, or None.
    """
    try:
        div_member = None
        # Try to get divisionMember component from entity
        if CC is not None:
            try:
                div_member = entity[CC.divisionMember]
            except:
                pass
        if div_member is None:
            try:
                div_member = _get_attr(entity, 'divisionMember')
            except:
                pass
        if div_member is None:
            return None

        division = _get_attr(div_member, 'division')
        if division is None or division == 0:
            return None

        return {
            'division': _safe_val(division),
            'divisionSign': _safe_val(_get_attr(div_member, 'divisionSign')),
            'isInSameDivision': _safe_val(_get_attr(div_member, 'isInSameDivision')),
        }
    except:
        return None


def _collect_division_map():
    """
    Collect division info for all players.
    Returns dict mapping playerId to division info.
    """
    div_map = {}

    # Try to get division info from marker entities or dedicated collection
    try:
        # First try: divisionMember as a standalone collection
        for entity in dataHub.getEntityCollections('divisionMember'):
            try:
                div_member = entity[CC.divisionMember] if CC else None
                if div_member is None:
                    div_member = entity
                player_id = _get_attr(div_member, 'playerId')
                if player_id is None:
                    # Try to get from parent entity
                    player_id = _get_attr(entity, 'playerId')
                if player_id is not None:
                    division = _get_attr(div_member, 'division')
                    if division and division > 0:
                        div_map[player_id] = {
                            'division': _safe_val(division),
                            'divisionSign': _safe_val(_get_attr(div_member, 'divisionSign')),
                            'isInSameDivision': _safe_val(_get_attr(div_member, 'isInSameDivision')),
                        }
            except:
                pass
    except:
        pass

    # Second try: Check marker entities if available
    try:
        for entity in dataHub.getEntityCollections('marker'):
            try:
                div_info = _extract_division_info(entity)
                if div_info:
                    # Try to find associated player ID
                    avatar = _get_attr(entity, 'avatar')
                    if avatar:
                        player_id = _get_attr(avatar, 'id')
                        if player_id is not None:
                            div_map[player_id] = div_info
            except:
                pass
    except:
        pass

    # Third try: Check avatar entities for division component
    try:
        for entity in dataHub.getEntityCollections('avatar'):
            try:
                avatar = entity[CC.avatar] if CC else entity
                player_id = _get_attr(avatar, 'id')
                if player_id is not None and player_id not in div_map:
                    div_info = _extract_division_info(entity)
                    if div_info:
                        div_map[player_id] = div_info
            except:
                pass
    except:
        pass

    return div_map


def _collect_all_ship_params():
    """
    Collect ship parameters for all players from shipBattleInfo collection.
    Uses dataHub as primary source for all ship data (consumables, TTX, identity).
    Returns list of dicts, one per player.
    """
    players = []
    avatar_map = {}
    battle_player_map = {}

    # Collect division info
    div_map = _collect_division_map()

    # Second, try battle.getPlayersInfo() for player identity data
    try:
        players_info = battle.getPlayersInfo()
        if players_info:
            for pid, pinfo in players_info.iteritems():
                try:
                    ship_info = _get_attr(pinfo, 'shipInfo')
                    player_name = _safe_val(_get_attr(pinfo, 'name'))
                    battle_player_map[pid] = {
                        'vehicleId': _safe_val(pid),
                        'playerId': _safe_val(pid),
                        'playerName': player_name,
                        'clanTag': _safe_val(_get_attr(pinfo, 'clanTag')),
                        'teamId': _safe_val(_get_attr(pinfo, 'teamId')),
                        'isBot': _safe_val(_get_attr(pinfo, 'isBot')),
                        'shipId': _safe_val(_get_attr(ship_info, 'id')) if ship_info else None,
                        'realm': _safe_val(_get_attr(pinfo, 'realm')),
                        'clanColor': _safe_val(_get_attr(pinfo, 'clanColor')),
                        'prebattleId': _safe_val(_get_attr(pinfo, 'prebattleId')),
                    }
                except Exception as ex:
                    _log('[DIAGNOSTIC] battle.getPlayersInfo() - failed to extract player %s: %s' % (pid, str(ex)))
        else:
            _log('[DIAGNOSTIC] battle.getPlayersInfo() returned None')
    except Exception as ex:
        _log('[ERROR] battle.getPlayersInfo() failed: %s' % str(ex))

    # Third, collect avatar info (may have additional data)
    try:
        avatar_collection = dataHub.getEntityCollections('avatar')
        if not avatar_collection:
            _log('[DIAGNOSTIC] avatar collection is empty')
        else:
            avatar_count = 0
            for entity in avatar_collection:
                try:
                    avatar = entity[CC.avatar]
                    avatar_id = _get_attr(avatar, 'id')
                    if avatar_id is not None:
                        avatar_map[avatar_id] = _extract_avatar_info(avatar)
                        avatar_count += 1
                except Exception as ex:
                    _log('[DIAGNOSTIC] Failed to extract avatar info: %s' % str(ex))
            _log('[DIAGNOSTIC] Successfully extracted %d avatar records' % avatar_count)
    except Exception as ex:
        _log('[ERROR] Failed to access avatar collection: %s' % str(ex))

    # Fourth, collect shipBattleInfo (computed parameters) and merge all identity sources
    try:
        ship_collection = dataHub.getEntityCollections('shipBattleInfo')
        if not ship_collection:
            _log('[ERROR-CRITICAL] shipBattleInfo collection is empty or failed to load')
            return []

        ship_count = 0
        for entity in ship_collection:
            try:
                ship = entity[CC.shipBattleInfo]
                player_id = _get_attr(ship, 'playerId')
                if player_id is None:
                    _log('[DIAGNOSTIC] shipBattleInfo entity missing playerId')
                    continue

                ship_count += 1

                # Start with battle.getPlayersInfo data (most reliable for identity)
                player_data = {}
                if player_id in battle_player_map:
                    player_data = dict(battle_player_map[player_id])

                # Merge avatar info (may have additional fields)
                avatar_info = avatar_map.get(player_id, {}) or {}
                for key, val in avatar_info.iteritems():
                    # Only copy if not already set or if current value is empty
                    if key not in player_data or player_data.get(key) in (None, ''):
                        player_data[key] = val

                # Ensure playerId is set
                if 'playerId' not in player_data or player_data.get('playerId') is None:
                    player_data['playerId'] = _safe_val(player_id)

                # Extract ship identity from shipBattleInfo (available at early timing!)
                ship_id = _get_attr(ship, 'shipId')
                if ship_id is not None:
                    player_data['shipId'] = _safe_val(ship_id)
                clone_ship_id = _get_attr(ship, 'cloneShipId')
                if clone_ship_id is not None:
                    player_data['cloneShipId'] = _safe_val(clone_ship_id)

                # Add division info if available
                if player_id in div_map:
                    player_data['divisionInfo'] = div_map[player_id]

                # Add isRealParams flag (indicates if params include player build modifiers)
                player_data['isRealParams'] = _safe_val(_get_attr(ship, 'isRealParams'))

                # Extract TTX parameters
                ttx_params = _extract_ship_ttx(ship)
                if ttx_params:
                    player_data['params'] = ttx_params

                # Extract consumable data using v5.1 parser (all parameters, both main and alt)
                cons_data = _extract_consumables(ship)
                if cons_data:
                    # Store mainConsumables and altConsumables arrays
                    player_data['mainConsumables'] = cons_data.get('mainConsumables', [])
                    player_data['altConsumables'] = cons_data.get('altConsumables', [])

                players.append(player_data)
            except Exception as ex:
                import traceback
                _log('[ERROR] Failed to extract shipBattleInfo for player_id: %s' % str(ex))
                _log('[TRACEBACK] %s' % traceback.format_exc())

        _log('[DIAGNOSTIC] Successfully extracted %d of %d shipBattleInfo records' % (len(players), ship_count))
    except Exception as ex:
        import traceback
        _log('[ERROR-CRITICAL] Failed to access shipBattleInfo collection: %s' % str(ex))
        _log('[TRACEBACK] %s' % traceback.format_exc())

    return players


def _write_json_file(path, data):
    """Write JSON data to file."""
    try:
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
        f = open(path, 'wb')
        f.write(text)
        f.close()
        _log('[DIAGNOSTIC] Successfully wrote BattleStart file: %s' % path)
    except Exception as ex:
        import sys
        _log('[ERROR] BattleStart write failed to %s: %s' % (path, str(sys.exc_info()[1])))


def _do_write_ship_params(trigger_name):
    """
    Collect and write ship params. Called from onPlayersListUpdated.
    Returns True if data was written successfully, False otherwise.
    Uses v5.1 retry mechanism - only succeeds if we get player data.
    """
    try:
        ts = int(time.time())
    except:
        ts = 0

    _log('[DIAGNOSTIC] _do_write_ship_params triggered by %s at timestamp %d' % (trigger_name, ts))

    players = _collect_all_ship_params()
    player_count = len(players)

    if player_count == 0:
        _log('[WARNING] No players found - data not ready yet (trigger: %s)' % trigger_name)
        return False

    players_with_consumables = sum(1 for p in players if len(p.get('mainConsumables', [])) > 0)
    _log('[DIAGNOSTIC] Collected %d players, %d with consumable data' % (player_count, players_with_consumables))

    # Build output data with v5.1 metadata
    data = {
        'version': MOD_VERSION,
        'schema': 'wowsbi-battlestart-v2',  # New schema version
        'ts': ts,
        'trigger': trigger_name,
        'playersCount': player_count,
        'timestamps': dict(_capture_timestamps),  # Include all diagnostic timestamps
        'players': players,
    }

    # Write stable output
    stable_path = MOD_PATH + '/BattleStart.json'
    _write_json_file(stable_path, data)

    # Write timestamped backup
    try:
        ts_str = time.strftime('%Y%m%d_%H%M%S', time.localtime(ts))
    except:
        ts_str = str(ts)
    backup_path = MOD_PATH + '/BattleStart_' + ts_str + '.json'
    _write_json_file(backup_path, data)

    _log('BattleStart JSON written: %d players' % player_count)
    return True


def _on_players_list_updated(*args, **kwargs):
    """Triggered when players list changes during loading screen.
    This event can fire multiple times. Use retry mechanism if data not ready yet."""
    global _captured_once

    if _captured_once:
        _log('[DIAGNOSTIC] _on_players_list_updated: already captured, skipping')
        return

    _log('[DIAGNOSTIC] _on_players_list_updated event fired')

    # Attempt to write ship parameters
    success = _do_write_ship_params('onPlayersListUpdated')

    # Check if we got data (count players in written file)
    # Only set flag if we successfully captured data
    if success:
        _captured_once = True


def _on_battle_end(*args, **kwargs):
    """Battle ended - reset captured flag for next battle."""
    global _captured_once, _capture_timestamps
    _captured_once = False
    _capture_timestamps = {}


def _on_battle_quit(*args, **kwargs):
    """Legacy handler for battle quit."""
    _on_battle_end(*args, **kwargs)


_log('BattleStart v%s loaded' % MOD_VERSION)

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
