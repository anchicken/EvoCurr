
from datetime import datetime
from sc2 import maps
import os
from sc2.bot_ai import BotAI
from sc2.data import Race, Difficulty
from sc2.ids.ability_id import AbilityId
from sc2.ids.effect_id import EffectId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.main import run_game
from sc2.player import Bot, Computer
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units
from sc2.ids.buff_id import BuffId
from python_sc2_test.run_pvt_map import ProtossBot
from python_sc2_test.run_zvt_3_map import EnhancedZergBot
import math
import random
import numpy as np
import numpy
from typing import List, Dict, Set, Optional, Union, Iterable
from math import atan2, pi, cos, sin


class BattleBot(BotAI):


    def __init__(self):
        super().__init__()
        # Formation center near the bottom of ramp choke (to hold choke defensively)
        self.formation_center = Point2((13, 15))
        self.army_state = "FORM_UP"
        self.engagement_distance = 18
        self.ghost_emp_cooldown = 0
        self.formation_ready = False

    async def on_step(self, iteration: int):
        if not self.formation_ready:
            await self.setup_formation()
            self.formation_ready = True

        await self.update_army_state()

        if self.army_state == "FORM_UP":
            await self.maintain_formation()
        else:
            await self.engage_enemy()

        if self.ghost_emp_cooldown > 0:
            self.ghost_emp_cooldown -= 1

    async def update_army_state(self):
        if not self.enemy_units.exists:
            self.army_state = "FORM_UP"
            return
        dist = self.enemy_units.center.distance_to(self.formation_center)
        self.army_state = "ENGAGE" if dist <= self.engagement_distance else "FORM_UP"

    async def setup_formation(self):
        # Position SiegeTanks defensively on low ground near choke, siege if possible
        tank_positions = [
            Point2((11, 13)), Point2((13, 13)), Point2((15, 13)),
            Point2((17, 14)), Point2((14, 15)), Point2((16, 15))
        ]
        tanks = self.units(UnitTypeId.SIEGETANK)
        for i, tank in enumerate(tanks):
            pos = tank_positions[i % len(tank_positions)]
            tank.move(pos)
            abilities = await self.get_available_abilities(tank)
            if AbilityId.SIEGEMODE_SIEGEMODE in abilities:
                tank(AbilityId.SIEGEMODE_SIEGEMODE)

        # Marauders in two rows behind tanks for frontline & slow enemy melee
        marauder_base = Point2((10, 16))
        marauders = self.units(UnitTypeId.MARAUDER)
        for i, m in enumerate(marauders):
            row = i // 6
            col = (i % 6) * 2
            m.move(marauder_base + Point2((col, row)))

        # Marines clustered in tight block behind frontline as DPS
        marine_base = Point2((9, 20))
        marines = self.units(UnitTypeId.MARINE)
        for i, marine in enumerate(marines):
            row = i // 8
            col = (i % 8) * 1.2
            marine.move(marine_base + Point2((col, row)))

        # Cyclones form right flank line to use Lock-On and harassment
        cyclone_base = Point2((18, 18))
        cyclones = self.units(UnitTypeId.CYCLONE)
        for i, cyclone in enumerate(cyclones):
            cyclone.move(cyclone_base + Point2((0, i * 2)))

        # Ghosts clumped further back cloaking and preparing EMP + Snipe
        ghost_base = Point2((13, 19))
        ghosts = self.units(UnitTypeId.GHOST)
        ghost_offsets = [
            Point2((-2, 0)), Point2((2, 0)), Point2((-4, 2)), Point2((4, 2)),
            Point2((-3, 4)), Point2((3, 4)), Point2((-5, 6)), Point2((5, 6))
        ]
        for i, ghost in enumerate(ghosts):
            pos = ghost_base + ghost_offsets[i % len(ghost_offsets)]
            ghost.move(pos)

        # Vikings positioned on higher ground near top ramp for AA defense/offense
        viking_base = Point2((18, 22))
        vikings = self.units(UnitTypeId.VIKINGFIGHTER)
        for i, viking in enumerate(vikings):
            viking.move(viking_base + Point2((i * 2, 0)))

        # Medivacs hover above bio units for healing support
        medivac_base = Point2((15, 21))
        medivacs = self.units(UnitTypeId.MEDIVAC)
        for i, medivac in enumerate(medivacs):
            offset = (i - len(medivacs) / 2) * 2.5
            medivac.move(medivac_base + Point2((offset, 0)))

        # WidowMines burrow near choke to control ramp and deny area
        mine_positions = [
            Point2((13, 13)), Point2((15, 13)), Point2((17, 13)),
            Point2((14, 12)), Point2((16, 12)), Point2((15, 11)),
            Point2((14, 14)), Point2((16, 14))
        ]
        mines = self.units(UnitTypeId.WIDOWMINE)
        for i, mine in enumerate(mines):
            pos = mine_positions[i % len(mine_positions)]
            mine.move(pos)
            abilities = await self.get_available_abilities(mine)
            if AbilityId.BURROWDOWN_WIDOWMINE in abilities:
                mine(AbilityId.BURROWDOWN_WIDOWMINE)

        # Ravens stay near ghosts to provide Interference Matrix and detection
        raven_base = Point2((13, 21))
        ravens = self.units(UnitTypeId.RAVEN)
        for i, raven in enumerate(ravens):
            offset = (i - len(ravens) / 2) * 2.5
            raven.move(raven_base + Point2((offset, 0)))

    async def maintain_formation(self):
        # Slowly advance formation center towards enemy but safely hold choke
        if self.enemy_units.exists:
            enemy_center = self.enemy_units.center
            dist = enemy_center.distance_to(self.formation_center)
            if 10 < dist < 22:
                self.formation_center = self.formation_center.towards(enemy_center, 0.3)

        # Control units in defensive posture
        await self.control_siege_tanks()
        await self.control_bio(engaging=False)
        await self.control_medivacs()
        await self.control_ghosts(engaging=False)
        await self.control_vikings(engaging=False)
        await self.control_cyclones()
        await self.control_widow_mines()
        await self.control_ravens()

    async def engage_enemy(self):
        # Aggressive engagement: stim, cloak, emp, snipe, lock-on, kiting
        await self.control_siege_tanks(engage=True)
        await self.control_bio(engaging=True)
        await self.control_medivacs()
        await self.control_ghosts(engaging=True)
        await self.control_vikings(engaging=True)
        await self.control_cyclones()
        await self.control_widow_mines()
        await self.control_ravens()
        await self.evade_aoe()

    async def control_siege_tanks(self, engage: bool = False):
        tanks = self.units(UnitTypeId.SIEGETANK) | self.units(UnitTypeId.SIEGETANKSIEGED)
        for tank in tanks:
            abilities = await self.get_available_abilities(tank)
            dist_to_center = tank.distance_to(self.formation_center)

            # Regroup if no enemies or too far
            if not self.enemy_units.exists or dist_to_center > 12:
                if tank.type_id == UnitTypeId.SIEGETANKSIEGED and AbilityId.UNSIEGE_UNSIEGE in abilities:
                    tank(AbilityId.UNSIEGE_UNSIEGE)
                tank.move(self.formation_center)
                continue

            closest_enemy = self.enemy_units.closest_to(tank.position)
            dist_to_enemy = tank.distance_to(closest_enemy)

            if tank.type_id == UnitTypeId.SIEGETANK:
                # Siege if enemy close enough and possible
                if dist_to_enemy <= 13 and AbilityId.SIEGEMODE_SIEGEMODE in abilities:
                    tank(AbilityId.SIEGEMODE_SIEGEMODE)
                elif dist_to_enemy > 14:
                    tank.move(self.formation_center)
            else:
                # Attack while sieged, unsiege if enemy too far
                tank.attack(closest_enemy)
                if dist_to_enemy > 14 and AbilityId.UNSIEGE_UNSIEGE in abilities:
                    tank(AbilityId.UNSIEGE_UNSIEGE)

    async def control_bio(self, engaging: bool):
        marines = self.units(UnitTypeId.MARINE)
        marauders = self.units(UnitTypeId.MARAUDER)

        melee_threats = self.enemy_units.of_type({UnitTypeId.ZEALOT})
        armored_psionic = self.enemy_units.of_type({
            UnitTypeId.STALKER, UnitTypeId.SENTRY, UnitTypeId.HIGHTEMPLAR,
            UnitTypeId.COLOSSUS, UnitTypeId.DISRUPTOR
        })

        for marine in marines:
            abilities = await self.get_available_abilities(marine)
            if not self.enemy_units.exists:
                if marine.distance_to(self.formation_center) > 5:
                    marine.move(self.formation_center)
                continue

            closest_enemy = self.enemy_units.closest_to(marine.position)
            dist = marine.distance_to(closest_enemy)

            # Stimpack when in range and healthy
            if dist <= 7 and AbilityId.EFFECT_STIM_MARINE in abilities and marine.health > 30:
                marine(AbilityId.EFFECT_STIM_MARINE)

            # Kite zealots aggressively
            if closest_enemy.type_id == UnitTypeId.ZEALOT and dist < 5:
                marine.move(marine.position.towards(closest_enemy.position, -4))
                continue

            if engaging:
                marine.attack(closest_enemy)
            else:
                if marine.distance_to(self.formation_center) > 6:
                    marine.move(self.formation_center)
                else:
                    marine.attack(closest_enemy)

        for marauder in marauders:
            abilities = await self.get_available_abilities(marauder)

            if not self.enemy_units.exists:
                if marauder.distance_to(self.formation_center) > 5:
                    marauder.move(self.formation_center)
                continue

            priority_targets = armored_psionic.closer_than(15, marauder.position)
            target = priority_targets.closest_to(marauder.position) if priority_targets.exists else self.enemy_units.closest_to(marauder.position)
            if not target:
                continue

            dist = marauder.distance_to(target)

            # Stim if target close and health good
            if dist <= 8 and AbilityId.EFFECT_STIM_MARAUDER in abilities and marauder.health > 60:
                marauder(AbilityId.EFFECT_STIM_MARAUDER)

            # Kite zealots as well
            if target.type_id == UnitTypeId.ZEALOT and dist < 5:
                marauder.move(marauder.position.towards(target.position, -3))
                continue

            if engaging:
                marauder.attack(target)
            else:
                if marauder.distance_to(self.formation_center) > 6:
                    marauder.move(self.formation_center)
                else:
                    marauder.attack(target)

    async def control_medivacs(self):
        medivacs = self.units(UnitTypeId.MEDIVAC)
        bio = self.units.of_type({UnitTypeId.MARINE, UnitTypeId.MARAUDER, UnitTypeId.GHOST})
        if not medivacs.exists or not bio.exists:
            return

        injured = bio.filter(lambda u: u.health < u.health_max * 0.85)

        for medivac in medivacs:
            if injured.exists and medivac.energy > 10:
                target = injured.closest_to(medivac.position)
                medivac(AbilityId.MEDIVACHEAL_HEAL, target)
            else:
                medivac.move(bio.center.towards(self.formation_center, 3))

    async def control_ghosts(self, engaging: bool):
        ghosts = self.units(UnitTypeId.GHOST)
        if not ghosts.exists or not self.enemy_units.exists:
            return

        templars = self.enemy_units(UnitTypeId.HIGHTEMPLAR)
        high_value = self.enemy_units.of_type({
            UnitTypeId.HIGHTEMPLAR, UnitTypeId.COLOSSUS, UnitTypeId.DISRUPTOR
        })

        for ghost in ghosts:
            abilities = await self.get_available_abilities(ghost)

            # Cloak if energy sufficient and not cloaked
            if AbilityId.BEHAVIOR_CLOAKON_GHOST in abilities and ghost.energy >= 50:
                ghost(AbilityId.BEHAVIOR_CLOAKON_GHOST)

            # EMP if templars clustered and cooldown ready
            if templars.exists and self.ghost_emp_cooldown == 0:
                cluster = templars.closer_than(5, templars.center)
                if cluster.exists and AbilityId.EMP_EMP in abilities and ghost.energy >= 75:
                    ghost(AbilityId.EMP_EMP, cluster.center)
                    self.ghost_emp_cooldown = 30
                    continue

            targets_for_snipe = high_value.closer_than(10, ghost.position)
            if targets_for_snipe.exists and AbilityId.SNIPE_SNIPE in abilities and ghost.energy >= 50:
                target = targets_for_snipe.closest_to(ghost.position)
                ghost(AbilityId.SNIPE_SNIPE, target)
                continue

            if engaging:
                target = self.enemy_units.closest_to(ghost.position)
                if target:
                    ghost.attack(target)
            else:
                if ghost.distance_to(self.formation_center) > 8:
                    ghost.move(self.formation_center)

    async def control_vikings(self, engaging: bool):
        vikings = self.units(UnitTypeId.VIKINGFIGHTER)
        if not vikings.exists or not self.enemy_units.exists:
            return

        priority_air = [
            self.enemy_units(UnitTypeId.CARRIER),
            self.enemy_units(UnitTypeId.TEMPEST),
            self.enemy_units(UnitTypeId.COLOSSUS)
        ]

        for viking in vikings:
            target = None
            for air_set in priority_air:
                if air_set.exists:
                    target = air_set.closest_to(viking.position)
                    break

            if not target:
                target = self.enemy_units.closest_to(viking.position)

            if target:
                viking.attack(target)

            # Keep vikings near formation center for safety
            if viking.distance_to(self.formation_center) > 15:
                viking.move(self.formation_center)

    async def control_cyclones(self):
        cyclones = self.units(UnitTypeId.CYCLONE)
        if not cyclones.exists or not self.enemy_units.exists:
            return

        armored_mech_targets = self.enemy_units.of_type({
            UnitTypeId.STALKER, UnitTypeId.COLOSSUS, UnitTypeId.SENTRY, UnitTypeId.TEMPEST
        })

        for cyclone in cyclones:
            abilities = await self.get_available_abilities(cyclone)

            if armored_mech_targets.exists:
                target = armored_mech_targets.closest_to(cyclone.position)
                if cyclone.distance_to(target) <= 8 and AbilityId.LOCKON_LOCKON in abilities:
                    cyclone(AbilityId.LOCKON_LOCKON, target)
                    continue

            target = self.enemy_units.closest_to(cyclone.position)
            if target:
                cyclone.attack(target)

    async def control_widow_mines(self):
        mines = self.units(UnitTypeId.WIDOWMINE)
        if not mines.exists:
            return

        for mine in mines:
            abilities = await self.get_available_abilities(mine)
            enemy_close = self.enemy_units.closer_than(12, mine.position).exists
            enemy_far = not self.enemy_units.closer_than(15, mine.position).exists

            if enemy_close and AbilityId.BURROWDOWN_WIDOWMINE in abilities:
                mine(AbilityId.BURROWDOWN_WIDOWMINE)
            elif enemy_far and AbilityId.BURROWUP_WIDOWMINE in abilities:
                mine(AbilityId.BURROWUP_WIDOWMINE)
                if mine.distance_to(self.formation_center) > 7:
                    mine.move(self.formation_center + Point2((0, -4)))

    async def control_ravens(self):
        ravens = self.units(UnitTypeId.RAVEN)
        if not ravens.exists or not self.enemy_units.exists:
            return

        matrix_targets = self.enemy_units.of_type({
            UnitTypeId.COLOSSUS, UnitTypeId.DISRUPTOR, UnitTypeId.HIGHTEMPLAR
        })

        for raven in ravens:
            abilities = await self.get_available_abilities(raven)
            if matrix_targets.exists and raven.energy >= 75:
                target = matrix_targets.closest_to(raven.position)
                if raven.distance_to(target) <= 9 and AbilityId.EFFECT_INTERFERENCEMATRIX in abilities:
                    raven(AbilityId.EFFECT_INTERFERENCEMATRIX, target)
                    continue

            if raven.distance_to(self.formation_center) > 12:
                raven.move(self.formation_center)

    async def evade_aoe(self):
        # Avoid enemy Psionic Storm and Disruptor orbs by moving away
        PSIONIC_STORM_ID = 23
        safe_distance = 4

        storms = [e for e in self.state.effects if e.id == PSIONIC_STORM_ID]
        disruptors = self.enemy_units(UnitTypeId.DISRUPTORPHASED)
        vulnerable = self.units.of_type({
            UnitTypeId.MARINE, UnitTypeId.MARAUDER, UnitTypeId.GHOST, UnitTypeId.MEDIVAC
        })

        for unit in vulnerable:
            for storm in storms:
                if unit.distance_to(storm.position) < safe_distance:
                    unit.move(unit.position.towards(storm.position, -safe_distance))
                    break
            for dis in disruptors:
                if unit.distance_to(dis.position) < safe_distance:
                    unit.move(unit.position.towards(dis.position, -safe_distance - 1))
                    break



if __name__ == '__main__':
    time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_name = time_str + "Example.SC2Replay"
    file_name = os.path.join("replay", file_name)
    time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    bot = BattleBot()
    result = run_game(maps.get('test1'), [Bot(Race.Random, bot), Bot(Race.Random, ProtossBot())], realtime=False, save_replay_as=file_name)
    print(result)
    print(bot.state.score.score)
    print(bot.state.score.total_damage_dealt_life)
    print(bot.state.score.total_damage_taken_life)
    print(bot.state.score.total_damage_taken_shields)
    print(len(bot.units))
    print(len(bot.enemy_units)+ len(bot.enemy_structures))
