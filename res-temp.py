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

    async def on_step(self, iteration: int):
        if iteration == 0:
            await self.initial_positioning()

        # Unit groupings
        bio = self.units.of_type({UnitTypeId.MARINE, UnitTypeId.MARAUDER})
        medivacs = self.units(UnitTypeId.MEDIVAC)
        tanks_all = self.units.of_type({UnitTypeId.SIEGETANK, UnitTypeId.SIEGETANKSIEGED})
        vikings = self.units(UnitTypeId.VIKINGFIGHTER)
        ghosts = self.units(UnitTypeId.GHOST)
        cyclones = self.units(UnitTypeId.CYCLONE)
        widowmines = self.units.of_type({UnitTypeId.WIDOWMINE, UnitTypeId.WIDOWMINEBURROWED})
        libs = self.units(UnitTypeId.LIBERATOR)
        ravens = self.units(UnitTypeId.RAVEN)

        # Unit control
        await self.control_marines()
        await self.control_marauders()
        await self.control_medivacs()
        await self.control_ghosts()
        await self.control_siegetanks()
        await self.control_vikingfighters()
        await self.control_cyclones()
        await self.control_widowmines()
        await self.control_ravens()
        await self.control_liberators()


    async def initial_positioning(self):
        """根据strategy positions初始化单位站位"""
        # 初始化 UnitTypeId.MARINE
        for i, u in enumerate(self.units(UnitTypeId.MARINE)):
            x = 10 + (i % 6) * 1
            y = 20 + (i // 6) * 1
            u.move(Point2((x, y)))
        # 初始化 UnitTypeId.MARAUDER
        for i, u in enumerate(self.units(UnitTypeId.MARAUDER)):
            x = 11 + (i % 4) * 1.5
            y = 21 + (i // 4) * 1.5
            u.move(Point2((x, y)))
        # 初始化 UnitTypeId.MEDIVAC
        for i, u in enumerate(self.units(UnitTypeId.MEDIVAC)):
            x = 9 + (i % 2) * 2
            y = 22 + (i // 2) * 2
            u.move(Point2((x, y)))
        # 初始化 UnitTypeId.GHOST
        for i, u in enumerate(self.units(UnitTypeId.GHOST)):
            x = 12 + (i % 3) * 1.5
            y = 19 + (i // 3) * 1.5
            u.move(Point2((x, y)))
        # 初始化 UnitTypeId.SIEGETANK
        for i, u in enumerate(self.units(UnitTypeId.SIEGETANK)):
            x = 14 + (i % 3) * 2
            y = 18 + (i // 3) * 2
            u.move(Point2((x, y)))
        # 初始化 UnitTypeId.VIKINGFIGHTER
        for i, u in enumerate(self.units(UnitTypeId.VIKINGFIGHTER)):
            x = 8 + (i % 3) * 1.5
            y = 24 + (i // 3) * 1.5
            u.move(Point2((x, y)))
        # 初始化 UnitTypeId.CYCLONE
        for i, u in enumerate(self.units(UnitTypeId.CYCLONE)):
            x = 13 + (i % 2) * 2
            y = 22 + (i // 2) * 2
            u.move(Point2((x, y)))
        # 初始化 UnitTypeId.WIDOWMINE
        for i, u in enumerate(self.units(UnitTypeId.WIDOWMINE)):
            x = 11 + (i % 3) * 1
            y = 18 + (i // 3) * 1
            u.move(Point2((x, y)))
        # 初始化 UnitTypeId.RAVEN
        for i, u in enumerate(self.units(UnitTypeId.RAVEN)):
            x = 9 + (i % 2) * 2
            y = 23 + (i // 2) * 2
            u.move(Point2((x, y)))
        # 初始化 UnitTypeId.LIBERATOR
        for i, u in enumerate(self.units(UnitTypeId.LIBERATOR)):
            x = 7 + (i % 2) * 2
            y = 24 + (i // 2) * 2
            u.move(Point2((x, y)))


    async def control_cyclones(self):
        cyclones = self.units(UnitTypeId.CYCLONE)
        enemies = self.enemy_units
        armored_targets = enemies.of_type([UnitTypeId.COLOSSUS, UnitTypeId.STALKER, UnitTypeId.SIEGETANK])

        for cyclone in cyclones:
            if armored_targets.exists:
                target = armored_targets.closest_to(cyclone)
                if AbilityId.LOCKON_LOCKON in await self.get_available_abilities(cyclone):
                    cyclone(AbilityId.LOCKON_LOCKON, target)
                else:
                    cyclone.attack(target)
            elif enemies.exists:
                cyclone.attack(enemies.closest_to(cyclone))


    async def control_ghosts(self):
        ghosts = self.units(UnitTypeId.GHOST)
        enemies = self.enemy_units
        high_templars = enemies(UnitTypeId.HIGHTEMPLAR)
        sentries = enemies(UnitTypeId.SENTRY)

        for ghost in ghosts:
            # EMP High Templars first
            if high_templars.exists and ghost.energy >= 75:
                ht = high_templars.closest_to(ghost)
                if ghost.distance_to(ht) < 10:
                    if AbilityId.EMP_EMP in await self.get_available_abilities(ghost):
                        ghost(AbilityId.EMP_EMP, ht.position)
                        continue

            # Snipe key targets
            snipe_targets = high_templars | sentries
            if snipe_targets.exists and ghost.energy >= 50:
                target = snipe_targets.closest_to(ghost)
                if ghost.distance_to(target) < 10:
                    if AbilityId.EFFECT_GHOSTSNIPE in await self.get_available_abilities(ghost):
                        ghost(AbilityId.EFFECT_GHOSTSNIPE, target)
                        continue

            # Default attack
            if enemies.exists:
                ghost.attack(enemies.closest_to(ghost))


    async def control_liberators(self):
        liberators = self.units(UnitTypeId.LIBERATOR)
        if not liberators.exists:
            return

        enemy_ground = self.enemy_units.not_flying
        enemy_air = self.enemy_units.flying

        for liberator in liberators:
            if enemy_ground.exists and not enemy_air.closer_than(8, liberator).exists:
                closest_ground = enemy_ground.closest_to(liberator)
                if liberator.distance_to(closest_ground) < 12:
                    if AbilityId.MORPH_LIBERATORAGMODE in await self.get_available_abilities(liberator):
                        liberator(AbilityId.MORPH_LIBERATORAGMODE, closest_ground.position)
                else:
                    liberator.move(closest_ground.position)
            elif enemy_air.exists:
                closest_air = enemy_air.closest_to(liberator)
                liberator.attack(closest_air)
            else:
                liberator.move(self.main_army_position)


    async def control_marauders(self):
        marauders = self.units(UnitTypeId.MARAUDER)
        enemies = self.enemy_units

        for marauder in marauders:
            abilities = await self.get_available_abilities(marauder)

            if AbilityId.EFFECT_STIM in abilities and enemies.closer_than(8, marauder):
                marauder(AbilityId.EFFECT_STIM)

            armored_targets = enemies.of_type([UnitTypeId.STALKER, UnitTypeId.SENTRY])
            if armored_targets:
                marauder.attack(armored_targets.closest_to(marauder))
            elif enemies:
                marauder.attack(enemies.closest_to(marauder))


    async def control_marines(self):
        marines = self.units(UnitTypeId.MARINE)
        enemies = self.enemy_units

        if not marines.exists or not enemies.exists:
            return

        priority_targets = enemies.of_type([UnitTypeId.STALKER, UnitTypeId.COLOSSUS])

        for unit in marines:
            if priority_targets.exists:
                target = priority_targets.closest_to(unit)
                if unit.distance_to(target) < 8:
                    if AbilityId.EFFECT_STIM in await self.get_available_abilities(unit) and unit.health_percentage > 0.6:
                        unit(AbilityId.EFFECT_STIM)
                    unit.attack(target)
                else:
                    unit.move(target.position)
            else:
                closest_enemy = enemies.closest_to(unit)
                if unit.distance_to(closest_enemy) < 6:
                    if AbilityId.EFFECT_STIM in await self.get_available_abilities(unit) and unit.health_percentage > 0.6:
                        unit(AbilityId.EFFECT_STIM)
                    unit.attack(closest_enemy)
                else:
                    unit.move(closest_enemy.position)


    async def control_medivacs(self):
        medivacs = self.units(UnitTypeId.MEDIVAC)
        if not medivacs.exists:
            return

        bio_units = self.units.of_type({UnitTypeId.MARINE, UnitTypeId.MARAUDER, UnitTypeId.GHOST})
        if not bio_units.exists:
            return

        # Find most injured bio units
        injured_units = bio_units.sorted(key=lambda u: u.health_percentage)

        for medivac in medivacs:
            if injured_units.exists and injured_units[0].health_percentage < 0.9:
                target_unit = injured_units[0]
                if medivac.distance_to(target_unit) > 5:
                    medivac.move(target_unit.position)
                elif AbilityId.MEDIVACHEAL_HEAL in await self.get_available_abilities(medivac):
                    medivac(AbilityId.MEDIVACHEAL_HEAL, target_unit)
            else:
                # Follow bio army center but maintain safe distance
                bio_center = bio_units.center
                safe_position = bio_center.offset(Point2((0, 6)))
                if medivac.distance_to(safe_position) > 3:
                    medivac.move(safe_position)


    async def control_ravens(self):
        ravens = self.units(UnitTypeId.RAVEN)
        enemies = self.enemy_units

        for raven in ravens:
            if AbilityId.EFFECT_ANTIARMORMISSILE in await self.get_available_abilities(raven) and raven.energy >= 75:
                priority = enemies.of_type([UnitTypeId.COLOSSUS, UnitTypeId.TEMPEST, UnitTypeId.CARRIER])
                if priority:
                    raven(AbilityId.EFFECT_ANTIARMORMISSILE, priority.closest_to(raven))

            if AbilityId.EFFECT_INTERFERENCEMATRIX in await self.get_available_abilities(raven) and raven.energy >= 50:
                disruptors = enemies(UnitTypeId.DISRUPTOR)
                if disruptors:
                    raven(AbilityId.EFFECT_INTERFERENCEMATRIX, disruptors.closest_to(raven))


    async def control_siegetanks(self):
        siege_tanks = self.units(UnitTypeId.SIEGETANK)
        enemies = self.enemy_units
        if not enemies.exists:
            return

        for tank in siege_tanks:
            if tank.distance_to(enemies.closest_to(tank)) < 12:
                if AbilityId.SIEGEMODE_SIEGEMODE in await self.get_available_abilities(tank):
                    tank(AbilityId.SIEGEMODE_SIEGEMODE)
            else:
                tank.move(Point2((14, 18)))


    async def control_vikingfighters(self):
        vikings = self.units(UnitTypeId.VIKINGFIGHTER)
        if not vikings.exists:
            return
        air_targets = self.enemy_units.flying
        colossi = self.enemy_units(UnitTypeId.COLOSSUS)
        tempests = self.enemy_units(UnitTypeId.TEMPEST)
        carriers = self.enemy_units(UnitTypeId.CARRIER)
        for vk in vikings:
            if colossi.exists:
                vk.attack(colossi.closest_to(vk))
            elif tempests.exists:
                vk.attack(tempests.closest_to(vk))
            elif carriers.exists:
                vk.attack(carriers.closest_to(vk))
            elif air_targets.exists:
                vk.attack(air_targets.closest_to(vk))
            else:
                vk.move(self.bio_line + Point2((0, 4)))


    async def control_widowmines(self):
        mines = self.units(UnitTypeId.WIDOWMINE)
        enemies = self.enemy_units
        for wm in mines:
            abilities = await self.get_available_abilities(wm)
            if enemies.in_attack_range_of(wm):
                if AbilityId.WIDOWMINEATTACK_WIDOWMINEATTACK in abilities:
                    wm(AbilityId.WIDOWMINEATTACK_WIDOWMINEATTACK, enemies.closest_to(wm))
            else:
                if AbilityId.BURROWDOWN_WIDOWMINE in abilities:
                    wm(AbilityId.BURROWDOWN_WIDOWMINE)




if __name__ == '__main__':
    time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_name = time_str + "Example.SC2Replay"
    file_name = os.path.join("replay", file_name)
    time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    bot = BattleBot()
    result = run_game(maps.get('pvt_bush'), [Bot(Race.Random, bot), Bot(Race.Random, ProtossBot())], realtime=False, save_replay_as=file_name)
    print(result)
    print(bot.state.score.score)
    print(bot.state.score.total_damage_dealt_life)
    print(bot.state.score.total_damage_taken_life)
    print(bot.state.score.total_damage_taken_shields)
    print(len(bot.units))
    print(len(bot.enemy_units)+ len(bot.enemy_structures))
