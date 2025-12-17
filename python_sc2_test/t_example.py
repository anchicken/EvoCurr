
from sc2 import maps
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
from typing import List, Dict, Set, Optional, Union

class BattleBot(BotAI):
    async def on_step(self, iteration: int):
        # Initialize and perform one-time setup
        if iteration == 0:
            self.setup_complete = False
            await self.initial_positioning()
            self.setup_complete = True
        
        # Group units to avoid redundant checks
        bio_units = self.units.of_type({UnitTypeId.MARINE, UnitTypeId.MARAUDER})
        medivacs = self.units(UnitTypeId.MEDIVAC)

        # Unified AOE avoidance for vulnerable units
        await self.avoid_aoe(bio_units + medivacs)

        # Execute control groups
        await self.control_siege_tanks()
        await self.control_ghosts()
        await self.control_bio(UnitTypeId.MARINE)
        await self.control_bio(UnitTypeId.MARAUDER)
        await self.control_medivacs()

    async def avoid_aoe(self, units: Units):
        storms = [e for e in self.state.effects if e.id == EffectId.PSISTORMPERSISTENT]
        disruptor_balls = self.enemy_units(UnitTypeId.DISRUPTORPHASED)
        
        threats = []
        # Psionic Storms have a radius of 1.5, but we use a larger buffer
        for storm in storms:
            threats.append((storm.position, 2.5)) 
        # Purification Nova has a radius of 1.5, but the visual is larger
        for ball in disruptor_balls:
            threats.append((ball.position, 2.5))

        for unit in units:
            for pos, radius in threats:
                if unit.distance_to(pos) < radius:
                    # Move unit 3 units away from the center of the threat
                    away = unit.position.towards(pos, -3)
                    unit.move(away)
                    break # Move to next unit once it's dodging one threat

    async def initial_positioning(self):
        # This function sets the initial formation of the army.
        
        # Tanks: Rear line
        for i, tank in enumerate(self.units(UnitTypeId.SIEGETANKSIEGED)):
            tank.move(Point2((15 + (i % 2), 15 + (i // 2))))

        # Marines: Grid formation
        for i, marine in enumerate(self.units(UnitTypeId.MARINE)):
            x = 8 + (i % 5) * 1.0
            y = 22 - (i // 5) * 1.0
            marine.move(Point2((x, y)))

        # Marauders: Front line
        for i, marauder in enumerate(self.units(UnitTypeId.MARAUDER)):
            x = 8 + (i % 4) * 1.5
            y = 20 - (i // 4) * 1.0
            marauder.move(Point2((x, y)))

        # Medivacs: Behind bio
        for i, medivac in enumerate(self.units(UnitTypeId.MEDIVAC)):
            medivac.move(Point2((6 + i, 20)))

        # Ghosts: Flanking and hidden
        for i, ghost in enumerate(self.units(UnitTypeId.GHOST)):
            ghost.move(Point2((20, 10 + i)))
        

    async def control_siege_tanks(self):
        siege_tanks = self.units(UnitTypeId.SIEGETANKSIEGED)
        sieged_tanks = self.units(UnitTypeId.SIEGETANKSIEGED)

        # Siege up tanks that are in position
        for tank in siege_tanks:
            # Move to siege position if not already there
            if tank.distance_to(Point2((15, 15))) > 2:
                continue
            
            if AbilityId.SIEGEMODE_SIEGEMODE in await self.get_available_abilities(tank):
                tank(AbilityId.SIEGEMODE_SIEGEMODE)
        
        # Control sieged tanks
        if sieged_tanks.exists:
            enemies = self.enemy_units
            if not enemies.exists:
                return
                
            priority_targets = enemies.of_type([UnitTypeId.COLOSSUS, UnitTypeId.STALKER, UnitTypeId.HIGHTEMPLAR, UnitTypeId.ZEALOT])
            
            for tank in sieged_tanks:
                # Find the best target in range
                targets_in_range = priority_targets.in_attack_range_of(tank)
                if targets_in_range:
                    # Prioritize the highest threat target (based on list order)
                    target = min(targets_in_range, key=lambda t: (t.type_id not in {UnitTypeId.COLOSSUS, UnitTypeId.HIGHTEMPLAR}, t.distance_to(tank)))
                    tank.attack(target)
                elif enemies.in_attack_range_of(tank).exists:
                    tank.attack(enemies.in_attack_range_of(tank).closest_to(tank))


    async def control_ghosts(self):
        ghosts = self.units(UnitTypeId.GHOST)
        if not ghosts.exists:
            return
            
        enemies = self.enemy_units
        high_templars = enemies(UnitTypeId.HIGHTEMPLAR)
        
        for ghost in ghosts:
            
            # Cloak if energy is sufficient
            if AbilityId.BEHAVIOR_CLOAKON_GHOST in await self.get_available_abilities(ghost):
                if ghost.energy >= 50:
                    ghost(AbilityId.BEHAVIOR_CLOAKON_GHOST)

            # Prioritize EMP on High Templars
            if high_templars.exists:
                target_ht = high_templars.closest_to(ghost)
                if ghost.distance_to(target_ht) <= 10:
                    if AbilityId.EMP_EMP in await self.get_available_abilities(ghost):
                        if ghost.energy >= 75:
                            ghost(AbilityId.EMP_EMP, target_ht.position)
                            continue # Skip to next ghost after casting
            
            # Snipe high value targets if no good EMP opportunity
            snipe_targets = enemies.of_type([UnitTypeId.COLOSSUS, UnitTypeId.HIGHTEMPLAR])
            if snipe_targets.exists:
                target_snipe = snipe_targets.closest_to(ghost)
                if AbilityId.SNIPE_SNIPE in await self.get_available_abilities(ghost):
                    if ghost.energy >= 50:
                        ghost(AbilityId.SNIPE_SNIPE, target_snipe)
                        continue
            # Default attack
            if enemies.exists:
                ghost.attack(enemies.closest_to(ghost))

    async def control_bio(self, unit_type: UnitTypeId):
        bio = self.units(unit_type)
        if not bio.exists:
            return

        enemies = self.enemy_units
        if not enemies.exists:
            return
        
        priority_targets = enemies.of_type([
            UnitTypeId.HIGHTEMPLAR, UnitTypeId.COLOSSUS, 
            UnitTypeId.DISRUPTOR, UnitTypeId.STALKER, UnitTypeId.ZEALOT
        ])

        for u in bio:
            target = None
            if priority_targets.exists:
                target = priority_targets.closest_to(u)
            elif enemies.exists:
                target = enemies.closest_to(u)

            if target:
                dist = u.distance_to(target)
                
                # Use Stim when engaging and health is not critical
                if AbilityId.EFFECT_STIM in await self.get_available_abilities(u):
                    if u.health_percentage > 0.5:
                        u(AbilityId.EFFECT_STIM)
                
                # Kite (move away from) melee units like Zealots if they get too close
                if target.type_id == UnitTypeId.ZEALOT and dist < 4:
                    u.move(u.position.towards(target.position, -2))
                else:
                    u.attack(target)

    async def control_medivacs(self):
        medivacs = self.units(UnitTypeId.MEDIVAC)
        if not medivacs.exists:
            return

        bio_units = self.units.of_type({UnitTypeId.MARINE, UnitTypeId.MARAUDER, UnitTypeId.GHOST})
        if not bio_units.exists:
            # If no bio, keep medivacs safe
            return

        # Find the most wounded bio unit overall
        injured = bio_units.sorted(key=lambda u: u.health_percentage)
        
        if injured:
            target_unit = injured[0]
            for medivac in medivacs:
                # Tell all medivacs to move toward the most injured unit
                medivac.move(target_unit.position)
                # Instruct all medivacs to heal continuously
                medivac(AbilityId.MEDIVACHEAL_HEAL)
        else:
            # If all units are healthy, medivacs can stay near the center of the bio army
            for medivac in medivacs:
                medivac.move(bio_units.center)

if __name__ == '__main__':
    bot = BattleBot()
    result = run_game(maps.get('test1'), [Bot(Race.Random, bot), Bot(Race.Protoss, ProtossBot())], realtime=True)
    print(result)
    print(bot.state.score.score)
    print(bot.state.score.total_damage_dealt_life)
    print(bot.state.score.total_damage_taken_life)
    print(bot.state.score.total_damage_taken_shields)
    print(len(bot.units))
    print(len(bot.enemy_units)+ len(bot.enemy_structures))
