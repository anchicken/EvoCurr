
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
import math
import random
import numpy as np
import numpy
from typing import List, Dict, Set, Optional, Union, Iterable
from math import atan2, pi, cos, sin


class BattleBot(BotAI):


    def __init__(self):
        super().__init__()
        self.army_state = "FORM_UP"
        self.ghost_emp_cooldown = 0
        self.formation_center = Point2((15, 15))
        self.engagement_distance = 12
        self.setup_complete = False

    async def on_step(self, iteration: int):
        if iteration == 0:
            await self.setup_formation()
            self.setup_complete = True
        
        if not self.setup_complete:
            return
            
        await self.update_army_state()
        
        if self.army_state == "FORM_UP":
            await self.maintain_formation()
        elif self.army_state == "ENGAGE":
            await self.engage_enemy()
        
        if self.ghost_emp_cooldown > 0:
            self.ghost_emp_cooldown -= 1

    async def update_army_state(self):
        if not self.enemy_units.exists:
            self.army_state = "FORM_UP"
            return
            
        enemy_distance = self.enemy_units.center.distance_to(self.formation_center)
        
        if enemy_distance < self.engagement_distance:
            self.army_state = "ENGAGE"
        else:
            self.army_state = "FORM_UP"

    async def setup_formation(self):
        tanks = self.units(UnitTypeId.SIEGETANK)
        for i, tank in enumerate(tanks):
            pos = self.formation_center + Point2((i * 2 - len(tanks) + 1, -6))
            tank.move(pos)
            if AbilityId.SIEGEMODE_SIEGEMODE in await self.safe_get_abilities(tank):
                tank(AbilityId.SIEGEMODE_SIEGEMODE)

        marines = self.units(UnitTypeId.MARINE)
        for i, marine in enumerate(marines):
            pos = self.formation_center + Point2((i * 1.5 - len(marines)/2, -2))
            marine.move(pos)

        marauders = self.units(UnitTypeId.MARAUDER)
        for i, marauder in enumerate(marauders):
            pos = self.formation_center + Point2((i * 2 - len(marauders) + 1, -4))
            marauder.move(pos)

        vikings = self.units(UnitTypeId.VIKINGFIGHTER)
        for i, viking in enumerate(vikings):
            pos = self.formation_center + Point2((i * 2 - len(vikings), 4))
            viking.move(pos)

        ghosts = self.units(UnitTypeId.GHOST)
        for i, ghost in enumerate(ghosts):
            flank_x = 8 * (-1 if i % 2 == 0 else 1)
            pos = self.formation_center + Point2((flank_x, -3))
            ghost.move(pos)

        medivacs = self.units(UnitTypeId.MEDIVAC)
        for i, medivac in enumerate(medivacs):
            pos = self.formation_center + Point2((i * 3 - len(medivacs), 8))
            medivac.move(pos)

        cyclones = self.units(UnitTypeId.CYCLONE)
        for i, cyclone in enumerate(cyclones):
            pos = self.formation_center + Point2((i * 2 - len(cyclones), 0))
            cyclone.move(pos)

        mines = self.units(UnitTypeId.WIDOWMINE)
        for i, mine in enumerate(mines):
            pos = self.formation_center + Point2((i * 3 - len(mines), -8))
            mine.move(pos)
            if AbilityId.BURROWDOWN_WIDOWMINE in await self.safe_get_abilities(mine):
                mine(AbilityId.BURROWDOWN_WIDOWMINE)

        ravens = self.units(UnitTypeId.RAVEN)
        for raven in ravens:
            raven.move(self.formation_center + Point2((0, 10)))

    async def maintain_formation(self):
        if self.enemy_units.exists:
            enemy_center = self.enemy_units.center
            direction = (enemy_center - self.formation_center).normalized
            
            if enemy_center.distance_to(self.formation_center) < 25:
                self.formation_center = self.formation_center.towards(enemy_center, 0.5)
        
        await self.control_siege_tanks()
        await self.control_vikings()
        await self.control_ghosts()
        await self.control_bio_units()
        await self.control_medivacs()
        await self.control_cyclones()
        await self.control_widow_mines()
        await self.control_ravens()

    async def engage_enemy(self):
        await self.control_siege_tanks()
        await self.control_vikings()
        await self.control_ghosts()
        await self.control_bio_units()
        await self.control_medivacs()
        await self.control_cyclones()
        await self.control_widow_mines()
        await self.control_ravens()
        await self.avoid_aoe()

    async def avoid_aoe(self):
        storms = [e for e in self.state.effects if e.id == EffectId.PSISTORMPERSISTENT]
        disruptors = self.enemy_units(UnitTypeId.DISRUPTORPHASED)
        
        vulnerable_units = self.units.of_type({
            UnitTypeId.MARINE, UnitTypeId.MARAUDER, UnitTypeId.GHOST, UnitTypeId.MEDIVAC
        })
        
        for unit in vulnerable_units:
            for storm in storms:
                if unit.distance_to(storm.position) < 3:
                    unit.move(unit.position.towards(storm.position, -4))
                    break
            for disruptor in disruptors:
                if unit.distance_to(disruptor.position) < 3:
                    unit.move(unit.position.towards(disruptor.position, -5))
                    break

    async def safe_get_abilities(self, unit: Unit):
        if not unit.is_ready:
            return []
        try:
            return await self.get_available_abilities(unit)
        except Exception:
            return []

    async def control_siege_tanks(self):
        tanks = self.units(UnitTypeId.SIEGETANK)
        sieged_tanks = self.units(UnitTypeId.SIEGETANKSIEGED)
        
        for tank in tanks:
            abilities = await self.safe_get_abilities(tank)
            if AbilityId.SIEGEMODE_SIEGEMODE in abilities and tank.distance_to(self.formation_center) < 10:
                tank(AbilityId.SIEGEMODE_SIEGEMODE)
        
        if sieged_tanks.exists and self.enemy_units.exists:
            priority_targets = self.enemy_units.of_type([
                UnitTypeId.COLOSSUS, UnitTypeId.HIGHTEMPLAR, UnitTypeId.DISRUPTOR
            ])
            
            for tank in sieged_tanks:
                if priority_targets.exists:
                    target = min(priority_targets, key=lambda t: t.distance_to(tank))
                    tank.attack(target)
                else:
                    closest_enemy = self.enemy_units.closest_to(tank.position)
                    if closest_enemy:
                        tank.attack(closest_enemy)

    async def control_vikings(self):
        vikings = self.units(UnitTypeId.VIKINGFIGHTER)
        if not vikings.exists or not self.enemy_units.exists:
            return
            
        carriers = self.enemy_units(UnitTypeId.CARRIER)
        tempests = self.enemy_units(UnitTypeId.TEMPEST)
        colossi = self.enemy_units(UnitTypeId.COLOSSUS)
        
        for viking in vikings:
            if carriers.exists:
                target = min(carriers, key=lambda c: c.distance_to(viking))
                viking.attack(target)
            elif tempests.exists:
                target = min(tempests, key=lambda t: t.distance_to(viking))
                viking.attack(target)
            elif colossi.exists:
                target = min(colossi, key=lambda c: c.distance_to(viking))
                viking.attack(target)
            else:
                closest_enemy = self.enemy_units.closest_to(viking.position)
                if closest_enemy:
                    viking.attack(closest_enemy)

    async def control_ghosts(self):
        ghosts = self.units(UnitTypeId.GHOST)
        if not ghosts.exists or not self.enemy_units.exists:
            return
            
        templars = self.enemy_units(UnitTypeId.HIGHTEMPLAR)
        
        for ghost in ghosts:
            abilities = await self.safe_get_abilities(ghost)
            
            if AbilityId.BEHAVIOR_CLOAKON_GHOST in abilities and ghost.energy >= 50:
                ghost(AbilityId.BEHAVIOR_CLOAKON_GHOST)
            
            if templars.exists and self.ghost_emp_cooldown == 0:
                templar_group = templars.closer_than(5, templars.center)
                if templar_group.exists:
                    if AbilityId.EMP_EMP in abilities and ghost.energy >= 75:
                        ghost(AbilityId.EMP_EMP, templar_group.center)
                        self.ghost_emp_cooldown = 25
                        continue
            
            snipe_targets = self.enemy_units.of_type([
                UnitTypeId.HIGHTEMPLAR, UnitTypeId.COLOSSUS, UnitTypeId.DISRUPTOR
            ])
            if snipe_targets.exists:
                target = min(snipe_targets, key=lambda t: t.distance_to(ghost))
                if ghost.distance_to(target) <= 10 and AbilityId.SNIPE_SNIPE in abilities and ghost.energy >= 50:
                    ghost(AbilityId.SNIPE_SNIPE, target)
                    continue
            
            closest_enemy = self.enemy_units.closest_to(ghost.position)
            if closest_enemy:
                ghost.attack(closest_enemy)

    async def control_bio_units(self):
        marines = self.units(UnitTypeId.MARINE)
        marauders = self.units(UnitTypeId.MARAUDER)
        
        for marine in marines:
            await self.control_marine(marine)
        
        for marauder in marauders:
            await self.control_marauder(marauder)

    async def control_marine(self, marine: Unit):
        if not self.enemy_units.exists:
            return
            
        abilities = await self.safe_get_abilities(marine)
        closest_enemy = self.enemy_units.closest_to(marine.position)
        
        if closest_enemy:
            dist = marine.distance_to(closest_enemy)
            
            if dist <= 7 and AbilityId.EFFECT_STIM_MARINE in abilities and marine.health > 30:
                marine(AbilityId.EFFECT_STIM_MARINE)
            
            if closest_enemy.type_id == UnitTypeId.ZEALOT and dist < 5:
                marine.move(marine.position.towards(closest_enemy.position, -4))
            else:
                marine.attack(closest_enemy)

    async def control_marauder(self, marauder: Unit):
        if not self.enemy_units.exists:
            return
            
        abilities = await self.safe_get_abilities(marauder)
        armored_targets = self.enemy_units.of_type([
            UnitTypeId.STALKER, UnitTypeId.COLOSSUS, UnitTypeId.SENTRY
        ])
        
        target = None
        if armored_targets.exists:
            target = min(armored_targets, key=lambda t: t.distance_to(marauder))
        else:
            target = self.enemy_units.closest_to(marauder.position)
        
        if target:
            dist = marauder.distance_to(target)
            
            if dist <= 8 and AbilityId.EFFECT_STIM_MARAUDER in abilities and marauder.health > 60:
                marauder(AbilityId.EFFECT_STIM_MARAUDER)
            
            if target.type_id == UnitTypeId.ZEALOT and dist < 4:
                marauder.move(marauder.position.towards(target.position, -3))
            else:
                marauder.attack(target)

    async def control_medivacs(self):
        medivacs = self.units(UnitTypeId.MEDIVAC)
        if not medivacs.exists:
            return
            
        bio = self.units.of_type({UnitTypeId.MARINE, UnitTypeId.MARAUDER, UnitTypeId.GHOST})
        
        for medivac in medivacs:
            if bio.exists:
                injured = bio.filter(lambda u: u.health < u.health_max * 0.8)
                if injured.exists and medivac.energy > 10:
                    target = min(injured, key=lambda u: u.health_percentage)
                    medivac(AbilityId.MEDIVACHEAL_HEAL, target)
                else:
                    if bio.exists:
                        medivac.move(bio.center.towards(self.formation_center, 8))
                    else:
                        medivac.move(self.formation_center + Point2((0, 12)))
            else:
                medivac.move(self.formation_center + Point2((0, 12)))

    async def control_cyclones(self):
        cyclones = self.units(UnitTypeId.CYCLONE)
        if not cyclones.exists or not self.enemy_units.exists:
            return
            
        mechanical_targets = self.enemy_units.of_type([
            UnitTypeId.STALKER, UnitTypeId.COLOSSUS, UnitTypeId.SENTRY, UnitTypeId.TEMPEST
        ])
        
        for cyclone in cyclones:
            abilities = await self.safe_get_abilities(cyclone)
            
            if mechanical_targets.exists:
                target = min(mechanical_targets, key=lambda t: t.distance_to(cyclone))
                if cyclone.distance_to(target) <= 8 and AbilityId.LOCKON_LOCKON in abilities:
                    cyclone(AbilityId.LOCKON_LOCKON, target)
                    continue
            
            closest_enemy = self.enemy_units.closest_to(cyclone.position)
            if closest_enemy:
                cyclone.attack(closest_enemy)

    async def control_widow_mines(self):
        mines = self.units(UnitTypeId.WIDOWMINE)
        if not mines.exists:
            return
            
        for mine in mines:
            abilities = await self.safe_get_abilities(mine)
            
            if self.enemy_units.closer_than(12, mine.position).exists:
                if AbilityId.BURROWDOWN_WIDOWMINE in abilities:
                    mine(AbilityId.BURROWDOWN_WIDOWMINE)
            elif not self.enemy_units.closer_than(15, mine.position).exists:
                if AbilityId.BURROWUP_WIDOWMINE in abilities:
                    mine(AbilityId.BURROWUP_WIDOWMINE)
                
                if self.enemy_units.exists:
                    mine.move(self.formation_center + Point2((0, -8)))

    async def control_ravens(self):
        ravens = self.units(UnitTypeId.RAVEN)
        if not ravens.exists or not self.enemy_units.exists:
            return
            
        matrix_targets = self.enemy_units.of_type([
            UnitTypeId.COLOSSUS, UnitTypeId.DISRUPTOR, UnitTypeId.HIGHTEMPLAR
        ])
        
        for raven in ravens:
            abilities = await self.safe_get_abilities(raven)
            
            if matrix_targets.exists and raven.energy >= 75:
                target = min(matrix_targets, key=lambda t: t.distance_to(raven))
                if raven.distance_to(target) <= 9 and AbilityId.EFFECT_INTERFERENCEMATRIX in abilities:
                    raven(AbilityId.EFFECT_INTERFERENCEMATRIX, target)
                    continue
            
            if self.units.exists:
                raven.move(self.units.center.towards(self.formation_center, 10))



if __name__ == '__main__':
    time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_name = time_str + "Example.SC2Replay"
    file_name = os.path.join("replay", file_name)
    time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    bot = BattleBot()
    result = run_game(maps.get('test1'), [Bot(Race.Random, bot), Bot(Race.Protoss, ProtossBot())], realtime=False, save_replay_as=file_name)
    print(result)
    print(bot.state.score.score)
    print(bot.state.score.total_damage_dealt_life)
    print(bot.state.score.total_damage_taken_life)
    print(bot.state.score.total_damage_taken_shields)
    print(len(bot.units))
    print(len(bot.enemy_units)+ len(bot.enemy_structures))
