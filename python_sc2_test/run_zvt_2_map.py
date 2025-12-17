"""
ZVT Enhanced Micro Management Bot - Zerg vs Terran
Complex scenario: Zergling + Baneling + Hydralisk + Broodlord vs Marine + Marauder + Helliontank + Ghost + Thor + Medivac
Advanced micro: targeted attacks, spell priorities, unit-specific tactics
"""

from sc2 import maps
from sc2.data import Race
from sc2.main import run_game
from sc2.player import Bot, Human
from sc2.bot_ai import BotAI
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.position import Point2

class EnhancedZergBot(BotAI):
    """
    Enhanced ZVT micro with complex unit composition:
    1. Zergling + Baneling: Fast melee assault
    2. Hydralisk: Ranged support and anti-air
    3. Broodlord: Long-range heavy artillery
    4. Infestor: Fungal Ghost priority, Neural Thor when possible
    5. Viper: Blinding Cloud on Thor clusters, Abduct key targets
    """

    def __init__(self):
        super().__init__()
        self.target_position = Point2((2.0, 2.0))
        self.attack_duration = 100
        # 单位威胁等级评分
        self.threat_priority = {
            UnitTypeId.GHOST: 10,           # 最高优先级
            UnitTypeId.THOR: 9,
            UnitTypeId.THORAP: 9,           # 防空状态的雷神
            UnitTypeId.HELLIONTANK: 7,      # 火车侠坦克模式
            UnitTypeId.HELLION: 6,          # 火车侠普通模式
            UnitTypeId.SIEGETANK: 8,
            UnitTypeId.SIEGETANKSIEGED: 9,
            UnitTypeId.MARINE: 5,
            UnitTypeId.MARAUDER: 6,
            UnitTypeId.MEDIVAC: 7
        }

    async def on_step(self, iteration: int):
        if iteration == 0:
            print("Enhanced ZVT Micro Bot initialized!")
            print("Our units: Zergling, Baneling, Hydralisk, Broodlord, Infestor, Viper")
            print("Enemy units: Marine, Marauder, Helliontank, Ghost, Thor, Medivac, Siegetank expected")

        await self.enhanced_micro_management(iteration)

        if iteration % 100 == 0:
            ground_units = self.units.filter(lambda u: not u.is_flying)
            print(f"Step {iteration}: Ground: {ground_units.amount}, Casters: {self.units.filter(lambda u: u.type_id in [UnitTypeId.INFESTOR, UnitTypeId.VIPER]).amount}, Enemy: {self.enemy_units.amount}")

    async def enhanced_micro_management(self, iteration: int):
        """增强版微操管理"""
        if not self.units.exists:
            return

        # 阶段性攻击控制
        if iteration < self.attack_duration:
            await self.ultralisk_assault()
            await self.broodlord_assault()
            await self.hydralisk_support()
            await self.zergling_control()
        else:
            await self.cleanup_survivors()
            
        # 施法单位持续控制
        await self.enhanced_infestor_control()
        await self.enhanced_viper_control()

    async def ultralisk_assault(self):
        """大龙突击指定位置 - 优先攻击高威胁目标"""
        ultralist = self.units(UnitTypeId.ULTRALISK)
        if not ultralist.exists:
            return

        for ultra in ultralist:
            # 检查是否有高优先级目标在攻击范围内
            nearby_enemies = self.enemy_units.closer_than(8, ultra.position)
            
            if nearby_enemies.exists:
                # 选择威胁等级最高的目标
                best_target = self.select_priority_target(nearby_enemies, ultra.position)
                if best_target:
                    ultra.attack(best_target)
                    continue
            
            # 没有近距离威胁，继续向目标位置进攻
            enemies_at_target = self.enemy_units.closer_than(5, self.target_position)
            if enemies_at_target.exists:
                # 目标点有敌人，攻击威胁最高的
                priority_target = self.select_priority_target(enemies_at_target, ultra.position)
                ultra.attack(priority_target if priority_target else enemies_at_target.closest_to(ultra.position))
            else:
                # 移动到目标位置
                ultra.attack(self.target_position)

    async def broodlord_assault(self):
        """母巢之主攻击 - 远程火力支援"""
        broodlords = self.units(UnitTypeId.BROODLORD)
        if not broodlords.exists:
            return

        for broodlord in broodlords:
            # 母巢之主优先攻击地面目标
            ground_enemies = self.enemy_units.filter(lambda u: not u.is_flying)
            if ground_enemies.exists:
                # 在射程内选择最高威胁目标
                in_range_enemies = ground_enemies.filter(lambda u: broodlord.distance_to(u) <= 10)
                if in_range_enemies.exists:
                    priority_target = self.select_priority_target(in_range_enemies, broodlord.position)
                    if priority_target:
                        broodlord.attack(priority_target)
                    else:
                        broodlord.attack(in_range_enemies.closest_to(broodlord.position))
                else:
                    # 移动到更好的攻击位置
                    closest_ground = ground_enemies.closest_to(broodlord.position)
                    attack_pos = broodlord.position.towards(closest_ground.position, 3)
                    broodlord.move(attack_pos)

    async def hydralisk_support(self):
        """刺蛇支援火力 - 优先对空，辅助地面"""
        hydralisks = self.units(UnitTypeId.HYDRALISK)
        if not hydralisks.exists:
            return

        for hydra in hydralisks:
            # 优先攻击空中单位
            air_enemies = self.enemy_units.filter(lambda u: u.is_flying)
            if air_enemies.exists:
                closest_air = air_enemies.closest_to(hydra.position)
                if hydra.distance_to(closest_air) <= hydra.ground_range:
                    hydra.attack(closest_air)
                    continue
            
            # 没有空中威胁，支援地面作战
            ground_enemies = self.enemy_units.filter(lambda u: not u.is_flying)
            if ground_enemies.exists:
                # 优先攻击雷神和其他高威胁单位
                priority_target = self.select_priority_target(ground_enemies, hydra.position)
                if priority_target and hydra.distance_to(priority_target) <= hydra.ground_range:
                    hydra.attack(priority_target)
                else:
                    # 攻击射程内最近的敌人
                    in_range_enemies = ground_enemies.filter(lambda u: hydra.distance_to(u) <= hydra.ground_range)
                    if in_range_enemies.exists:
                        hydra.attack(in_range_enemies.closest_to(hydra.position))

    async def zergling_control(self):
        """小狗控制 - 快速近战突击"""
        zerglings = self.units(UnitTypeId.ZERGLING)
        banelings = self.units(UnitTypeId.BANELING)
        
        # 小狗攻击 - 优先生物单位
        for zergling in zerglings:
            if self.enemy_units.exists:
                # 优先攻击生物单位
                bio_targets = self.enemy_units.filter(lambda u: not u.is_flying and
                    u.type_id in [UnitTypeId.MARINE, UnitTypeId.MARAUDER, UnitTypeId.GHOST])
                
                if bio_targets.exists:
                    closest_bio = bio_targets.closest_to(zergling.position)
                    zergling.attack(closest_bio)
                else:
                    # 攻击其他地面单位
                    ground_enemies = self.enemy_units.filter(lambda u: not u.is_flying)
                    if ground_enemies.exists:
                        zergling.attack(ground_enemies.closest_to(zergling.position))
        
        # 爆虫控制 - 简单攻击，不做复杂自爆逻辑
        for baneling in banelings:
            if self.enemy_units.exists:
                # 直接攻击最近的地面敌人
                ground_enemies = self.enemy_units.filter(lambda u: not u.is_flying)
                if ground_enemies.exists:
                    baneling.attack(ground_enemies.closest_to(baneling.position))

    async def cleanup_survivors(self):
        """清理残余敌人 - 智能目标选择"""
        combat_units = self.units.filter(lambda u: u.type_id in [
            UnitTypeId.ULTRALISK, UnitTypeId.HYDRALISK, UnitTypeId.ZERGLING, 
            UnitTypeId.BANELING, UnitTypeId.BROODLORD, UnitTypeId.CORRUPTOR
        ])

        for unit in combat_units:
            if self.enemy_units.exists:
                # 为每个单位选择最适合的目标
                if unit.type_id == UnitTypeId.ULTRALISK:
                    # 大龙优先攻击地面重装单位
                    ground_targets = self.enemy_units.filter(lambda u: not u.is_flying)
                    target = self.select_priority_target(ground_targets, unit.position)
                elif unit.type_id == UnitTypeId.BROODLORD:
                    # 母巢之主攻击地面单位
                    ground_targets = self.enemy_units.filter(lambda u: not u.is_flying)
                    target = self.select_priority_target(ground_targets, unit.position)
                elif unit.type_id == UnitTypeId.HYDRALISK:
                    # 刺蛇优先空中，其次地面
                    air_targets = self.enemy_units.filter(lambda u: u.is_flying)
                    if air_targets.exists:
                        target = air_targets.closest_to(unit.position)
                    else:
                        target = self.select_priority_target(self.enemy_units, unit.position)
                elif unit.type_id == UnitTypeId.BANELING:
                    # 爆虫直接攻击最近敌人
                    target = self.enemy_units.closest_to(unit.position)
                else:
                    # 其他单位攻击最近敌人
                    target = self.enemy_units.closest_to(unit.position)
                
                if target:
                    unit.attack(target)

    def select_priority_target(self, enemy_units, from_position):
        """智能目标选择 - 基于威胁等级和距离"""
        if not enemy_units.exists:
            return None
        
        best_target = None
        best_score = -1
        
        for enemy in enemy_units:
            # 威胁等级评分
            threat_score = self.threat_priority.get(enemy.type_id, 3)
            
            # 距离因子 (距离越近分数越高)
            distance = from_position.distance_to(enemy.position)
            distance_score = max(0, 15 - distance) / 15  # 15格内线性递减
            
            # 血量因子 (残血目标优先)
            health_factor = 1.5 if enemy.health_percentage < 0.3 else 1.0
            
            # 综合评分
            total_score = threat_score * (1 + distance_score) * health_factor
            
            if total_score > best_score:
                best_score = total_score
                best_target = enemy
        
        return best_target

    async def enhanced_infestor_control(self):
        """增强版感染虫控制 - 优先Fungal幽灵，机会控制雷神"""
        infestors = self.units(UnitTypeId.INFESTOR)
        if not infestors.exists:
            return

        for infestor in infestors:
            spell_cast = False
            
            # 最高优先级：Fungal幽灵
            if infestor.energy >= 75:
                ghosts = self.enemy_units.filter(lambda u: u.type_id == UnitTypeId.GHOST)
                
                if ghosts.exists:
                    # 寻找最佳Fungal位置（覆盖最多幽灵）
                    best_ghost_target = None
                    max_ghosts_hit = 0
                    
                    for ghost in ghosts:
                        if infestor.distance_to(ghost) <= 10:  # Fungal射程
                            ghosts_in_area = ghosts.closer_than(2.5, ghost.position).amount
                            if ghosts_in_area > max_ghosts_hit:
                                max_ghosts_hit = ghosts_in_area
                                best_ghost_target = ghost
                    
                    if best_ghost_target and max_ghosts_hit >= 1:
                        available_abilities = await self.get_available_abilities(infestor)
                        if AbilityId.FUNGALGROWTH_FUNGALGROWTH in available_abilities:
                            print(f"Infestor FUNGAL on {max_ghosts_hit} GHOST(S) - Priority target!")
                            infestor(AbilityId.FUNGALGROWTH_FUNGALGROWTH, best_ghost_target.position)
                            spell_cast = True

            # 次优先级：Neural控制雷神
            if not spell_cast and infestor.energy >= 100:
                thors = self.enemy_units.filter(lambda u: u.type_id in [UnitTypeId.THOR, UnitTypeId.THORAP])
                
                if thors.exists:
                    closest_thor = thors.closest_to(infestor.position)
                    if infestor.distance_to(closest_thor) <= 9:  # Neural射程
                        available_abilities = await self.get_available_abilities(infestor)
                        if AbilityId.NEURALPARASITE_NEURALPARASITE in available_abilities:
                            print(f"Infestor NEURAL PARASITE on THOR - High value target!")
                            infestor(AbilityId.NEURALPARASITE_NEURALPARASITE, closest_thor)
                            spell_cast = True

            # 第三优先级：Fungal其他生物单位集群
            if not spell_cast and infestor.energy >= 75:
                bio_units = self.enemy_units.filter(lambda u: not u.is_flying and
                    u.type_id in [UnitTypeId.MARINE, UnitTypeId.MARAUDER, UnitTypeId.HELLIONTANK])
                
                if bio_units.exists:
                    best_bio_target = None
                    max_units_hit = 0
                    
                    for bio in bio_units:
                        if infestor.distance_to(bio) <= 10:
                            units_in_range = bio_units.closer_than(2.5, bio.position).amount
                            if units_in_range > max_units_hit:
                                max_units_hit = units_in_range
                                best_bio_target = bio
                    
                    if best_bio_target and max_units_hit >= 3:  # 至少3个单位才释放
                        available_abilities = await self.get_available_abilities(infestor)
                        if AbilityId.FUNGALGROWTH_FUNGALGROWTH in available_abilities:
                            print(f"Infestor FUNGAL on {max_units_hit} bio units")
                            infestor(AbilityId.FUNGALGROWTH_FUNGALGROWTH, best_bio_target.position)
                            spell_cast = True

            # 安全位置控制
            await self.maintain_infestor_safety(infestor)

    async def enhanced_viper_control(self):
        """增强版毒蛇控制 - 优先对雷神致盲云雾"""
        vipers = self.units(UnitTypeId.VIPER)
        if not vipers.exists:
            return

        for viper in vipers:
            # 保持安全距离
            if await self.maintain_viper_safety(viper):
                continue

            spell_cast = False

            # 最高优先级：对雷神集群使用致盲云雾
            if viper.energy >= 100:
                thors = self.enemy_units.filter(lambda u: u.type_id in [UnitTypeId.THOR, UnitTypeId.THORAP])
                
                if thors.exists:
                    best_thor_pos = None
                    max_thors_affected = 0
                    
                    for thor in thors:
                        if viper.distance_to(thor) <= 11:  # 致盲云雾射程
                            # 计算云雾范围内的雷神数量（云雾半径约3.5）
                            thors_in_cloud = thors.closer_than(3.5, thor.position).amount
                            if thors_in_cloud > max_thors_affected:
                                max_thors_affected = thors_in_cloud
                                best_thor_pos = thor.position
                    
                    if best_thor_pos and max_thors_affected >= 1:
                        available_abilities = await self.get_available_abilities(viper)
                        if AbilityId.BLINDINGCLOUD_BLINDINGCLOUD in available_abilities:
                            print(f"Viper BLINDING CLOUD on {max_thors_affected} THOR(S) - Priority!")
                            viper(AbilityId.BLINDINGCLOUD_BLINDINGCLOUD, best_thor_pos)
                            spell_cast = True

            # 次优先级：绑架关键目标
            if not spell_cast and viper.energy >= 75:
                # 优先级：幽灵 > 医疗运输机 > 攻城坦克
                abduct_targets = self.enemy_units.filter(lambda u: u.type_id in [
                    UnitTypeId.GHOST, UnitTypeId.MEDIVAC, UnitTypeId.SIEGETANKSIEGED
                ])
                
                if abduct_targets.exists:
                    # 按优先级排序
                    priority_order = [UnitTypeId.GHOST, UnitTypeId.MEDIVAC, UnitTypeId.SIEGETANKSIEGED]
                    target = None
                    
                    for unit_type in priority_order:
                        candidates = abduct_targets.filter(lambda u: u.type_id == unit_type)
                        if candidates.exists:
                            closest = candidates.closest_to(viper.position)
                            if viper.distance_to(closest) <= 9:  # 绑架射程
                                target = closest
                                break
                    
                    if target:
                        available_abilities = await self.get_available_abilities(viper)
                        if AbilityId.EFFECT_ABDUCT in available_abilities:
                            print(f"Viper ABDUCT on {target.type_id}")
                            viper(AbilityId.EFFECT_ABDUCT, target)
                            spell_cast = True

            # 第三优先级：对坦克集群致盲云雾
            if not spell_cast and viper.energy >= 100:
                tanks = self.enemy_units.filter(lambda u: 
                    u.type_id in [UnitTypeId.SIEGETANK, UnitTypeId.SIEGETANKSIEGED])
                
                if tanks.exists:
                    best_tank_pos = None
                    max_tanks_affected = 0
                    
                    for tank in tanks:
                        if viper.distance_to(tank) <= 11:
                            tanks_in_cloud = tanks.closer_than(3.5, tank.position).amount
                            if tanks_in_cloud > max_tanks_affected:
                                max_tanks_affected = tanks_in_cloud
                                best_tank_pos = tank.position
                    
                    if best_tank_pos and max_tanks_affected >= 2:
                        available_abilities = await self.get_available_abilities(viper)
                        if AbilityId.BLINDINGCLOUD_BLINDINGCLOUD in available_abilities:
                            print(f"Viper BLINDING CLOUD on {max_tanks_affected} tanks")
                            viper(AbilityId.BLINDINGCLOUD_BLINDINGCLOUD, best_tank_pos)

    async def maintain_viper_safety(self, viper):
        """维持毒蛇安全距离"""
        if not self.enemy_units.exists:
            return False
            
        closest_enemy = self.enemy_units.closest_to(viper.position)
        if closest_enemy.distance_to(viper) < 3:  # 增加安全距离
            # 朝友军地面单位方向撤退
            ground_allies = self.units.filter(lambda u: not u.is_flying and 
                u.type_id in [UnitTypeId.ULTRALISK, UnitTypeId.HYDRALISK, UnitTypeId.ZERGLING, UnitTypeId.BROODLORD])
            
            if ground_allies.exists:
                safe_pos = viper.position.towards(ground_allies.center, -5)
                viper.move(safe_pos)
                return True
        return False

    async def maintain_infestor_safety(self, infestor):
        """维持感染虫安全距离"""
        if not self.enemy_units.exists:
            return
            
        # 检查危险距离内的敌人
        dangerous_enemies = self.enemy_units.closer_than(6, infestor.position)
        if dangerous_enemies.exists:
            # 寻找安全撤退位置
            ground_allies = self.units.filter(lambda u: not u.is_flying and 
                u.type_id in [UnitTypeId.ULTRALISK, UnitTypeId.HYDRALISK, UnitTypeId.ZERGLING, UnitTypeId.BROODLORD])
            
            if ground_allies.exists:
                retreat_pos = infestor.position.towards(ground_allies.center, -3)
                infestor.move(retreat_pos)
            else:
                # 没有地面单位掩护，向地图中心撤退
                map_center = Point2((self.game_info.map_size.x / 2, self.game_info.map_size.y / 2))
                retreat_pos = infestor.position.towards(map_center, -3)
                infestor.move(retreat_pos)


def main():
    try:
        run_game(
            maps.get("flat_test_5_final"), 
            [
                Human(Race.Terran, fullscreen=True), 
                Bot(Race.Zerg, EnhancedZergBot(), fullscreen=False)
            ], 
            realtime=True
        )
    except Exception as e:
        print(f"Game ended with exception: {e}")
        pass


if __name__ == "__main__":
    main()