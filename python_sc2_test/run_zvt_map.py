"""
ZVT Micro Management Bot - Zerg vs Terran
Simple and effective: attack target, cast spells, clean up survivors
"""

from sc2 import maps
from sc2.data import Race
from sc2.main import run_game
from sc2.player import Bot, Human
from sc2.bot_ai import BotAI
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.position import Point2

class ZergBot(BotAI):
    """
    Simple ZVT micro:
    1. Attack target point (2.0, 2.0) for 10 seconds
    2. Then attack surviving enemies
    3. Cast spells when available
    """

    def __init__(self):
        super().__init__()
        self.target_position = Point2((2.0, 2.0))
        self.attack_duration = 100  #

    async def on_step(self, iteration: int):
        if iteration == 0:
            print("ZVT Micro Bot initialized!")

        await self.micro_management(iteration)

        if iteration % 100 == 0:
            print(f"Step {iteration}: Units: {self.units.amount}, Enemy: {self.enemy_units.amount}")

    async def micro_management(self, iteration: int):
        """Main micro management"""
        if not self.units.exists:
            return

        # Control combat units
        if iteration < self.attack_duration:
            await self.attack_target()
        else:
            await self.attack_survivors()
            
        # Always control casters every step
        await self.control_vipers()
        await self.control_infestors()

    async def attack_target(self):
        """Attack target point (2.0, 2.0)"""
        combat_units = self.units.filter(lambda u: u.type_id in [
            UnitTypeId.ZERGLING, UnitTypeId.BANELING, UnitTypeId.ULTRALISK, UnitTypeId.CORRUPTOR
        ])

        for unit in combat_units:
            unit.attack(self.target_position)

    async def attack_survivors(self):
        """Attack surviving enemies"""
        combat_units = self.units.filter(lambda u: u.type_id in [
            UnitTypeId.ZERGLING, UnitTypeId.BANELING, UnitTypeId.ULTRALISK, UnitTypeId.CORRUPTOR
        ])

        for unit in combat_units:
            if self.enemy_units.exists:
                closest_enemy = self.enemy_units.closest_to(unit.position)
                unit.attack(closest_enemy)



    async def control_vipers(self):
        """蝰蛇微操 - 优化技能使用：对坦克用致盲云雾，对解放者用绑架"""
        vipers = self.units(UnitTypeId.VIPER)
        if not vipers.exists:
            return

        current_time = self.time

        for viper in vipers:
            # 保持安全距离
            if self.enemy_units.exists:
                closest_enemy = self.enemy_units.closest_to(viper.position)
                if closest_enemy.distance_to(viper) < 7:
                    # 朝己方单位方向撤退
                    if self.units.exists:
                        safe_pos = viper.position.towards(self.units.center, -4)
                        viper.move(safe_pos)
                        continue

            # 技能使用逻辑
            if viper.energy >= 75:
                if viper.energy >= 100:
                    tanks = self.enemy_units.filter(lambda u: 
                        u.type_id == UnitTypeId.SIEGETANK or 
                        u.type_id == UnitTypeId.SIEGETANKSIEGED)

                    if tanks.exists:
                        # 寻找坦克集群
                        best_tank_pos = None
                        max_tanks_affected = 0

                        for tank in tanks:
                            if viper.distance_to(tank) <= 11:  # 致盲云雾射程
                                tanks_in_range = tanks.closer_than(3.5, tank.position).amount
                                if tanks_in_range > max_tanks_affected:
                                    max_tanks_affected = tanks_in_range
                                    best_tank_pos = tank.position

                        if best_tank_pos and max_tanks_affected >= 1:
                            available_abilities = await self.get_available_abilities(viper)
                            if AbilityId.BLINDINGCLOUD_BLINDINGCLOUD in available_abilities:
                                print(f"Viper using BLINDING CLOUD on {max_tanks_affected} tanks!")
                                viper(AbilityId.BLINDINGCLOUD_BLINDINGCLOUD, best_tank_pos)
                                continue
                # 优先对解放者使用绑架
                liberators = self.enemy_units.filter(lambda u: u.type_id == UnitTypeId.LIBERATOR)
                deployed_liberators = liberators.filter(lambda u: u.distance_to(viper.position) <= 9)

                if deployed_liberators.exists:
                    target = deployed_liberators.closest_to(viper.position)
                    available_abilities = await self.get_available_abilities(viper)
                    if AbilityId.EFFECT_ABDUCT in available_abilities:
                        print(f"Viper using ABDUCT on Liberator!")
                        viper(AbilityId.EFFECT_ABDUCT, target)
                        continue

                # 对坦克使用致盲云雾


                # 备选：对其他重要单位使用绑架
                other_high_value = self.enemy_units.filter(lambda u:
                    u.type_id == UnitTypeId.SIEGETANK or
                    u.type_id == UnitTypeId.SIEGETANKSIEGED or
                    u.type_id == UnitTypeId.GHOST)

                if other_high_value.exists:
                    target = other_high_value.closest_to(viper.position)
                    if viper.distance_to(target) <= 9:
                        available_abilities = await self.get_available_abilities(viper)
                        if AbilityId.EFFECT_ABDUCT in available_abilities:
                            print(f"Viper using ABDUCT on {target.type_id}!")
                            viper(AbilityId.EFFECT_ABDUCT, target)
                            continue

            # 如果没有技能可用，保持安全位置
            if self.units.exists:
                ground_units = self.units.filter(lambda u: not u.is_flying)
                if ground_units.exists:
                    safe_pos = ground_units.center
                    if viper.distance_to(safe_pos) > 8:
                        viper.move(safe_pos)

    

    async def control_infestors(self):
        """Infestor spells: fungal bio, neural high value"""
        infestors = self.units(UnitTypeId.INFESTOR)
        if not infestors.exists:
            return

        for infestor in infestors:
            spell_cast = False
            
            # Fungal on bio units - find best position
            if infestor.energy >= 75:
                bio_units = self.enemy_units.filter(lambda u: not u.is_flying and
                    u.type_id in [UnitTypeId.MARINE, UnitTypeId.MARAUDER])
                
                if bio_units.exists:
                    # Find position that hits the most bio units
                    best_target = None
                    max_units_hit = 0
                    
                    for bio in bio_units:
                        if infestor.distance_to(bio) <= 10:  # Fungal range
                            # Count units within fungal radius (2.5)
                            units_in_range = bio_units.closer_than(2.5, bio.position).amount
                            if units_in_range > max_units_hit:
                                max_units_hit = units_in_range
                                best_target = bio
                    
                    if best_target and max_units_hit >= 2:  # Only if hits 2+ units
                        available_abilities = await self.get_available_abilities(infestor)
                        if AbilityId.FUNGALGROWTH_FUNGALGROWTH in available_abilities:
                            print(f"Infestor casting FUNGAL on {max_units_hit} units!")
                            infestor(AbilityId.FUNGALGROWTH_FUNGALGROWTH, best_target.position)
                            spell_cast = True

            # Neural parasite on high value targets
            if not spell_cast and infestor.energy >= 100:
                high_value = self.enemy_units.filter(lambda u: u.type_id in [
                    UnitTypeId.SIEGETANKSIEGED, UnitTypeId.MEDIVAC, UnitTypeId.GHOST
                ])
                
                if high_value.exists:
                    target_hv = high_value.closest_to(infestor.position)
                    if infestor.distance_to(target_hv) <= 9:
                        available_abilities = await self.get_available_abilities(infestor)
                        if AbilityId.NEURALPARASITE_NEURALPARASITE in available_abilities:
                            print(f"Infestor casting NEURAL on {target_hv.type_id}!")
                            infestor(AbilityId.NEURALPARASITE_NEURALPARASITE, target_hv)
                            spell_cast = True

            # Stay safe - only retreat if in immediate danger  
            if self.enemy_units.exists:
                closest_enemy = self.enemy_units.closest_to(infestor.position)
                if closest_enemy.distance_to(infestor) < 5:  # Only retreat if very close
                    if self.units.exists:
                        ground_units = self.units.filter(lambda u: u.type_id in [
                            UnitTypeId.ZERGLING, UnitTypeId.BANELING, UnitTypeId.ULTRALISK
                        ])
                        if ground_units.exists:
                            retreat_pos = infestor.position.towards(ground_units.center, -2)
                            infestor.move(retreat_pos)
                        else:
                            # No ground units, just move back a bit
                            retreat_pos = Point2((infestor.position.x + 2, infestor.position.y + 2))
                            infestor.move(retreat_pos)


def main():
    try:
        run_game(maps.get("flat_test_4_final"), [Human(Race.Terran, fullscreen=True), Bot(Race.Zerg, ZergBot(), fullscreen=False)], realtime=True)
    except Exception as e:
        print(f"Game ended with exception: {e}")
        pass


if __name__ == "__main__":
    main()