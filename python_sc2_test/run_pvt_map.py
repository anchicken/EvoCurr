"""
PVT Micro Management Bot - Protoss vs Terran
Specialized micro agent focusing on unit control without production.
"""

from sc2 import maps
from sc2.data import Race
from sc2.main import run_game
from sc2.player import Bot, Human
from sc2.bot_ai import BotAI
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.position import Point2
import math
import random

class ProtossBot(BotAI):
    """
    Micro agent for PVT:
    Our units: charge zealot, blink stalker, colossus, high templar, disruptor.
    Enemy units: marine, marauder, medivac, ghost, viking, siege tank, liberator.
    """

    def __init__(self):
        super().__init__()
        self.last_storm_time = {}  # 记录每个高圣堂武士的上次风暴时间
        self.last_disruptor_time = {}  # 记录每个分裂者的上次攻击时间
        self.disruptor_target_positions = []  # 记录已经被瞄准的位置，避免重复轰炸
        self.disruptor_cooldowns = {}  # 记录每个disruptor的技能冷却时间
        self.last_global_disruptor_shot = 0  # 记录全局最后一次disruptor释放时间
        self.purification_novas = {}  # 记录净化新星球的控制
        self.last_archon_morph_time = 0  # 记录上次尝试合成Archon的时间
        self.sentry_force_fields = {}  # 记录力场位置和时间
        self.sentry_guardian_shields = {}  # 记录守护之盾使用时间
        self.dt_blink_cooldowns = {}  # 记录暗黑圣堂武士闪烁冷却
        self.tempest_last_target = {}  # 记录风暴战舰最后攻击目标

    async def on_step(self, iteration: int):
        if iteration == 0:
            print("PVT Micro Bot initialized!")

        # 主要微操逻辑
        await self.micro_management()

        # 状态输出
        if iteration % 100 == 0:
            print(f"Step {iteration}: Units: {self.units.amount}, Enemy: {self.enemy_units.amount}")

    async def micro_management(self):
        """主要微操管理函数"""
        if not self.units.exists:
            return

        # 获取敌方单位
        enemy_units = self.enemy_units
        if not enemy_units.exists:
            return

        # 分别处理不同类型的单位
        await self.control_zealots()
        await self.control_stalkers()
        await self.control_colossi()
        await self.control_high_templars()
        await self.control_archons()
        await self.control_disruptors()
        await self.control_purification_novas()
        await self.control_tempests()
        await self.control_carriers()
        await self.control_sentries()
        await self.control_dark_templars()

    async def control_zealots(self):
        """狂热者微操 - 永远向前冲锋，不后退"""
        zealots = self.units(UnitTypeId.ZEALOT)
        if not zealots.exists:
            return

        enemy_ground = self.enemy_units.filter(lambda u: not u.is_flying)
        if not enemy_ground.exists:
            return

        for zealot in zealots:
            # 狂热者永远不后退，一直向前进攻
            # 寻找最近的敌方地面单位
            closest_enemy = enemy_ground.closest_to(zealot.position)

            # 如果有冲锋能力且距离合适，使用冲锋
            if (zealot.distance_to(closest_enemy) > 4 and
                zealot.distance_to(closest_enemy) < 8 and
                AbilityId.EFFECT_CHARGE in await self.get_available_abilities(zealot)):
                zealot(AbilityId.EFFECT_CHARGE, closest_enemy)
            else:
                # 普通攻击，永远向前
                zealot.attack(closest_enemy)

    async def control_stalkers(self):
        """追猎者微操 - 护盾被打完后闪烁撤退，然后继续进攻"""
        stalkers = self.units(UnitTypeId.STALKER)
        if not stalkers.exists:
            return

        # 优先目标：空中单位 (Viking, Liberator)
        air_targets = self.enemy_units.filter(lambda u: u.is_flying and
                                            (u.type_id == UnitTypeId.VIKING or
                                             u.type_id == UnitTypeId.LIBERATOR))

        for stalker in stalkers:
            # 神族经典操作：护盾被打完就闪烁，但不等恢复，继续输出
            if (stalker.shield_percentage <= 0.1 and  # 护盾几乎没有
                stalker.health_percentage > 0.3 and  # 血量还够
                AbilityId.EFFECT_BLINK_STALKER in await self.get_available_abilities(stalker)):
                if self.units.exists:
                    # 向后闪烁一下即可，不需要等护盾恢复
                    blink_pos = stalker.position.towards(self.units.center, 6)  # 距离缩短
                    stalker(AbilityId.EFFECT_BLINK_STALKER, blink_pos)
                    # 闪烁后立即继续攻击，不continue

            # 优先攻击空中单位
            if air_targets.exists:
                closest_air = air_targets.closest_to(stalker.position)
                if stalker.distance_to(closest_air) <= stalker.air_range:
                    stalker.attack(closest_air)
                else:
                    # 移动到攻击范围内
                    stalker.move(closest_air.position)
            else:
                # 没有空中目标时攻击其他敌人
                if self.enemy_units.exists:
                    target = self.enemy_units.closest_to(stalker.position)
                    stalker.attack(target)

                    # 如果敌人太近，后撤保持距离（但不是因为血量）
                    if target.distance_to(stalker) < 3:
                        retreat_pos = stalker.position.towards(target.position, -3)
                        stalker.move(retreat_pos)

    async def control_colossi(self):
        """巨像微操 - 专门攻击Marine和Marauder制造AOE伤害"""
        colossi = self.units(UnitTypeId.COLOSSUS)
        if not colossi.exists:
            return

        # 优先目标：Marine和Marauder
        priority_targets = self.enemy_units.filter(lambda u: not u.is_flying and
                                                 (u.type_id == UnitTypeId.MARINE or
                                                  u.type_id == UnitTypeId.MARAUDER))

        for colossus in colossi:
            # 优先攻击Marine和Marauder密集区域
            if priority_targets.exists:
                # 寻找最密集的Marine/Marauder群
                best_target = None
                max_nearby_enemies = 0

                for enemy in priority_targets:
                    nearby_enemies = priority_targets.closer_than(2, enemy.position).amount
                    if nearby_enemies > max_nearby_enemies:
                        max_nearby_enemies = nearby_enemies
                        best_target = enemy

                if best_target:
                    colossus.attack(best_target)
                else:
                    # 攻击最近的Marine/Marauder
                    colossus.attack(priority_targets.closest_to(colossus.position))
            else:
                # 没有优先目标时攻击其他地面单位
                enemy_ground = self.enemy_units.filter(lambda u: not u.is_flying)
                if enemy_ground.exists:
                    colossus.attack(enemy_ground.closest_to(colossus.position))

            # 躲避空中威胁
            air_threats = self.enemy_units.filter(lambda u: u.is_flying and u.can_attack_ground)
            if air_threats.exists:
                closest_air = air_threats.closest_to(colossus.position)
                if closest_air.distance_to(colossus) < 8:
                    if self.units.exists:
                        retreat_pos = colossus.position.towards(closest_air.position, -4)
                        colossus.move(retreat_pos)

    async def control_high_templars(self):
        """高圣堂武士微操 - Feedback反馈Ghost，放闪电风暴，能量不足时合成执政官"""
        templars = self.units(UnitTypeId.HIGHTEMPLAR)
        if not templars.exists:
            return


        # 合成执政官：把能量低于50的高圣堂武士放在列表里，然后挨个操作
        if self.units(UnitTypeId.HIGHTEMPLAR).amount >= 2:
            current_time = self.time
            if current_time - self.last_archon_morph_time > 3.0:  # 3秒冷却
                # 创建低能量圣堂武士列表
                low_energy_templars = []
                for templar in self.units(UnitTypeId.HIGHTEMPLAR).ready:
                    if templar.energy < 50:
                        low_energy_templars.append(templar)

                # 如果有至少2个能量不足的圣堂武士，让它们都执行合成指令
                if len(low_energy_templars) >= 2:
                    for templar in low_energy_templars:
                        templar(AbilityId.MORPH_ARCHON)
                    self.last_archon_morph_time = current_time

        for templar in templars:
            # 优先使用Feedback反馈Ghost
            ghosts = self.enemy_units.filter(lambda u: u.type_id == UnitTypeId.GHOST)
            if (ghosts.exists and 75>templar.energy >= 50 and
                AbilityId.FEEDBACK_FEEDBACK in await self.get_available_abilities(templar)):

                closest_ghost = ghosts.closest_to(templar.position)
                if templar.distance_to(closest_ghost) <= 9:  # Feedback射程
                    templar(AbilityId.FEEDBACK_FEEDBACK, closest_ghost)
                    continue
                else:
                    # 移动到Feedback范围内
                    templar.move(closest_ghost.position)
                    continue

            # 检查能量是否足够释放心灵风暴
            if templar.energy >= 75:
                # 寻找密集的敌方单位群释放风暴
                enemy_ground = self.enemy_units.filter(lambda u: not u.is_flying)
                if enemy_ground.exists:
                    best_storm_pos = None
                    max_targets = 0

                    for enemy in enemy_ground:
                        # 计算以该敌人为中心的风暴能命中多少单位
                        targets_in_storm = enemy_ground.closer_than(1.5, enemy.position).amount
                        if targets_in_storm > max_targets and targets_in_storm >= 3:
                            max_targets = targets_in_storm
                            best_storm_pos = enemy.position

                    # 释放风暴
                    if (best_storm_pos and
                        AbilityId.PSISTORM_PSISTORM in await self.get_available_abilities(templar)):
                        templar(AbilityId.PSISTORM_PSISTORM, best_storm_pos)
                        self.last_storm_time[templar.tag] = self.time
                        continue
            
            # 能量不足或没有合适目标时，保持安全距离
            if self.enemy_units.exists:
                closest_enemy = self.enemy_units.closest_to(templar.position)
                if closest_enemy.distance_to(templar) < 6:
                    if self.units.exists:
                        safe_pos = templar.position.towards(closest_enemy.position, -4)
                        templar.move(safe_pos)

    async def control_archons(self):
        """执政官微操 - 前线坦克，吸收伤害"""
        archons = self.units(UnitTypeId.ARCHON)
        if not archons.exists:
            return

        for archon in archons:
            # 执政官作为前线坦克，主动寻找敌人
            if self.enemy_units.exists:
                # 优先攻击地面单位
                enemy_ground = self.enemy_units.filter(lambda u: not u.is_flying)
                if enemy_ground.exists:
                    closest_enemy = enemy_ground.closest_to(archon.position)
                    archon.attack(closest_enemy)
                else:
                    # 没有地面单位时攻击空中单位
                    archon.attack(self.enemy_units.closest_to(archon.position))

    async def control_tempests(self):
        """风暴战舰微操 - 专门对付重甲单位和空中单位"""
        tempests = self.units(UnitTypeId.TEMPEST)
        if not tempests.exists:
            return

        # 优先目标：Colossus、Carrier、Battlecruiser、重装单位
        priority_air_targets = self.enemy_units.filter(lambda u: u.is_flying and
                                                    (u.type_id == UnitTypeId.BATTLECRUISER or
                                                    u.type_id == UnitTypeId.CARRIER or
                                                    u.type_id == UnitTypeId.LIBERATOR))

        priority_ground_targets = self.enemy_units.filter(lambda u: not u.is_flying and
                                                        (u.type_id == UnitTypeId.COLOSSUS or
                                                        u.type_id == UnitTypeId.SIEGETANK or
                                                        u.type_id == UnitTypeId.THOR))

        for tempest in tempests:
            target = None
            
            # 优先攻击空中重型单位
            if priority_air_targets.exists:
                target = priority_air_targets.closest_to(tempest.position)
            # 其次攻击地面重型单位
            elif priority_ground_targets.exists:
                closest_ground = priority_ground_targets.closest_to(tempest.position)
                if tempest.distance_to(closest_ground) <= tempest.ground_range:
                    target = closest_ground
            # 最后攻击其他空中单位
            else:
                air_targets = self.enemy_units.filter(lambda u: u.is_flying)
                if air_targets.exists:
                    target = air_targets.closest_to(tempest.position)

            if target:
                # 保持最佳攻击距离
                if target.is_flying:
                    attack_range = tempest.air_range - 1
                else:
                    attack_range = tempest.ground_range - 1

                if tempest.distance_to(target) <= attack_range:
                    tempest.attack(target)
                    self.tempest_last_target[tempest.tag] = target.tag
                else:
                    # 移动到攻击范围内
                    tempest.move(target.position)

            # 躲避近距离威胁
            close_threats = self.enemy_units.filter(lambda u: u.distance_to(tempest) < 6 and
                                                (u.type_id == UnitTypeId.VIKING or
                                                    u.type_id == UnitTypeId.STALKER))
            if close_threats.exists:
                # 后撤保持距离
                retreat_pos = tempest.position.towards(close_threats.center, -4)
                tempest.move(retreat_pos)

    async def control_carriers(self):
        """航空母舰微操 - 拦截机管理和位置控制"""
        carriers = self.units(UnitTypeId.CARRIER)
        if not carriers.exists:
            return

        for carrier in carriers:
            # 检查拦截机数量，自动生产拦截机
            if (carrier.health_percentage > 0.3 and  # 血量足够时才生产
                AbilityId.BUILD_INTERCEPTORS in await self.get_available_abilities(carrier)):
                # 如果拦截机不足8个，继续生产
                carrier(AbilityId.BUILD_INTERCEPTORS)

            # 攻击逻辑 - 优先攻击空中单位
            air_targets = self.enemy_units.filter(lambda u: u.is_flying)
            ground_targets = self.enemy_units.filter(lambda u: not u.is_flying)

            target = None
            if air_targets.exists:
                # 优先攻击空中威胁
                air_threats = air_targets.filter(lambda u: u.type_id == UnitTypeId.VIKING or
                                            u.type_id == UnitTypeId.CORRUPTOR)
                if air_threats.exists:
                    target = air_threats.closest_to(carrier.position)
                else:
                    target = air_targets.closest_to(carrier.position)
            elif ground_targets.exists:
                # 攻击防空单位优先
                aa_units = ground_targets.filter(lambda u: u.can_attack_air)
                if aa_units.exists:
                    target = aa_units.closest_to(carrier.position)
                else:
                    target = ground_targets.closest_to(carrier.position)

            if target:
                # 保持安全攻击距离
                safe_distance = 8 if target.can_attack_air else 6
                
                if carrier.distance_to(target) > safe_distance:
                    # 移动到攻击范围
                    move_pos = carrier.position.towards(target.position, 3)
                    carrier.move(move_pos)
                else:
                    carrier.attack(target)

            # 受伤严重时后撤
            if carrier.health_percentage < 0.3:
                if self.units.exists:
                    safe_pos = carrier.position.towards(self.units.center, 5)
                    carrier.move(safe_pos)

    async def control_sentries(self):
        """哨兵微操 - 力场和守护之盾"""
        sentries = self.units(UnitTypeId.SENTRY)
        if not sentries.exists:
            return

        current_time = self.time

        # 清理过期的力场记录
        self.sentry_force_fields = {pos: time for pos, time in self.sentry_force_fields.items() 
                                if current_time - time < 15}  # 力场持续15秒

        for sentry in sentries:
            # 优先使用守护之盾
            if (sentry.energy >= 75 and 
                sentry.tag not in self.sentry_guardian_shields or 
                current_time - self.sentry_guardian_shields.get(sentry.tag, 0) > 20):  # 20秒冷却
                
                # 检查附近是否有友军需要护盾
                nearby_friendlies = self.units.closer_than(4, sentry.position)
                if nearby_friendlies.amount >= 3:  # 至少3个友军时使用
                    if AbilityId.GUARDIANSHIELD_GUARDIANSHIELD in await self.get_available_abilities(sentry):
                        sentry(AbilityId.GUARDIANSHIELD_GUARDIANSHIELD)
                        self.sentry_guardian_shields[sentry.tag] = current_time
                        continue

            # 使用力场分割敌军
            if sentry.energy >= 50:
                # 寻找合适的力场位置
                enemy_ground = self.enemy_units.filter(lambda u: not u.is_flying)
                if enemy_ground.exists:
                    # 寻找敌军密集区域
                    for enemy in enemy_ground:
                        nearby_enemies = enemy_ground.closer_than(2, enemy.position)
                        if nearby_enemies.amount >= 3:  # 至少3个敌军聚集
                            # 检查是否已经有力场
                            force_field_pos = enemy.position
                            too_close_to_existing = False
                            for existing_pos in self.sentry_force_fields:
                                if force_field_pos.distance_to(existing_pos) < 2:
                                    too_close_to_existing = True
                                    break
                            
                            # 确保不会困住友军
                            friendly_in_range = self.units.closer_than(2.5, force_field_pos)
                            
                            if (not too_close_to_existing and 
                                not friendly_in_range.exists and
                                sentry.distance_to(force_field_pos) <= 9):  # 力场释放范围
                                
                                if AbilityId.FORCEFIELD_FORCEFIELD in await self.get_available_abilities(sentry):
                                    sentry(AbilityId.FORCEFIELD_FORCEFIELD, force_field_pos)
                                    self.sentry_force_fields[force_field_pos] = current_time
                                    continue

            # 保持安全位置
            if self.enemy_units.exists:
                closest_enemy = self.enemy_units.closest_to(sentry.position)
                if closest_enemy.distance_to(sentry) < 4:
                    if self.units.exists:
                        safe_pos = sentry.position.towards(closest_enemy.position, -3)
                        sentry.move(safe_pos)
                elif sentry.distance_to(closest_enemy) > 8:
                    # 跟上部队
                    if self.units.exists:
                        follow_pos = sentry.position.towards(self.units.center, 2)
                        sentry.move(follow_pos)
    
    async def control_dark_templars(self):
        """暗黑圣殿武士微操 - 隐身刺杀和闪烁"""
        dark_templars = self.units(UnitTypeId.DARKTEMPLAR)
        if not dark_templars.exists:
            return

        current_time = self.time

        # 清理过期的闪烁冷却记录
        self.dt_blink_cooldowns = {tag: time for tag, time in self.dt_blink_cooldowns.items()
                                if current_time - time < 10}  # 假设闪烁冷却10秒

        for dt in dark_templars:
            # 优先目标：高价值单位
            priority_targets = self.enemy_units.filter(lambda u: not u.is_flying and
                                                    (u.type_id == UnitTypeId.SIEGETANK or
                                                    u.type_id == UnitTypeId.GHOST or
                                                    u.type_id == UnitTypeId.MEDIVAC or
                                                    u.type_id == UnitTypeId.MARINE))

            # 检测威胁单位（有侦测能力的）
            detector_threats = self.enemy_units.filter(lambda u: 
                                                    u.type_id == UnitTypeId.RAVEN or
                                                    u.type_id == UnitTypeId.MISSILETURRET or
                                                    u.type_id == UnitTypeId.GHOST)

            # 如果生命值过低，使用闪烁撤退（如果有的话）
            if (dt.health_percentage < 0.3 and 
                dt.tag not in self.dt_blink_cooldowns and
                detector_threats.exists):
                
                closest_detector = detector_threats.closest_to(dt.position)
                if dt.distance_to(closest_detector) < 8:
                    # 模拟闪烁撤退（实际DT可能没有闪烁，这里假设有）
                    if self.units.exists:
                        blink_pos = dt.position.towards(closest_detector.position, -6)
                        dt.move(blink_pos)  # 用移动代替闪烁
                        self.dt_blink_cooldowns[dt.tag] = current_time
                        continue

            # 攻击逻辑
            if priority_targets.exists:
                target = priority_targets.closest_to(dt.position)
                
                # 如果附近有探测器，谨慎行动
                nearby_detectors = detector_threats.closer_than(6, dt.position)
                if nearby_detectors.exists:
                    # 优先击杀探测器
                    closest_detector = nearby_detectors.closest_to(dt.position)
                    if dt.distance_to(closest_detector) <= dt.ground_range:
                        dt.attack(closest_detector)
                    else:
                        # 绕后偷袭
                        flank_pos = closest_detector.position + Point2((
                            random.uniform(-3, 3), random.uniform(-3, 3)
                        ))
                        dt.move(flank_pos)
                else:
                    # 没有探测威胁，正常攻击
                    if dt.distance_to(target) <= dt.ground_range:
                        dt.attack(target)
                    else:
                        # 隐身接近
                        dt.move(target.position)
            else:
                # 没有优先目标，攻击最近的敌军
                if self.enemy_units.exists:
                    ground_enemies = self.enemy_units.filter(lambda u: not u.is_flying)
                    if ground_enemies.exists:
                        closest_enemy = ground_enemies.closest_to(dt.position)
                        
                        # 检查探测威胁
                        nearby_detectors = detector_threats.closer_than(8, dt.position)
                        if nearby_detectors.exists:
                            # 有探测威胁，保持距离或绕开
                            safe_pos = dt.position.towards(nearby_detectors.center, -4)
                            dt.move(safe_pos)
                        else:
                            # 安全，可以攻击
                            if dt.distance_to(closest_enemy) <= dt.ground_range:
                                dt.attack(closest_enemy)
                            else:
                                dt.move(closest_enemy.position)

            # 受伤严重时撤退到安全位置
            if dt.health_percentage < 0.2:
                if self.units.exists:
                    safe_retreat = dt.position.towards(self.units.center, 6)
                    dt.move(safe_retreat)

    async def control_disruptors(self):
        """分裂者微操 - 净化新星制造AOE伤害，专门打Marine/Ghost/Marauder"""
        disruptors = self.units(UnitTypeId.DISRUPTOR)
        if not disruptors.exists:
            return

        # 清理过期的目标位置记录（1秒后清理，更快的轮换）
        current_time = self.time
        self.disruptor_target_positions = [
            (pos, time) for pos, time in self.disruptor_target_positions
            if current_time - time < 1.0  # 缩短到1秒
        ]

        # 更新冷却时间记录 - 缩短CD检查时间，提高释放频率
        for disruptor_tag in list(self.disruptor_cooldowns.keys()):
            if current_time - self.disruptor_cooldowns[disruptor_tag] >= 12.0:  # 缩短到12秒
                del self.disruptor_cooldowns[disruptor_tag]

        # 为每个disruptor分配不同的攻击方向
        disruptor_list = list(disruptors)

        for i, disruptor in enumerate(disruptor_list):
            # 检查技能是否在冷却中
            if disruptor.tag in self.disruptor_cooldowns:
                # 技能在CD中，保持安全位置
                await self.position_disruptor_safely(disruptor)
                continue

            # 检查全局释放间隔（确保disruptor之间间隔1秒释放）
            if current_time - self.last_global_disruptor_shot < 1.0:
                # 还没到释放时间，保持位置
                await self.position_disruptor_safely(disruptor)
                continue

            # 检查是否可以使用净化新星
            available_abilities = await self.get_available_abilities(disruptor)
            if AbilityId.EFFECT_PURIFICATIONNOVA in available_abilities:

                # 寻找最佳AOE目标位置 - 专门针对小型单位
                priority_targets = self.enemy_units.filter(lambda u: not u.is_flying and
                                                         (u.type_id == UnitTypeId.MARINE or
                                                          u.type_id == UnitTypeId.GHOST or
                                                          u.type_id == UnitTypeId.MARAUDER))

                if priority_targets.exists:
                    best_target_pos = None
                    max_damage_potential = 0

                    # 根据disruptor索引分配不同的攻击区域，更小的扇形确保更多disruptor同时工作
                    sector_angle = (i * 45) % 360  # 每个disruptor负责45度扇形区域

                    for enemy in priority_targets:
                        # 检查射程限制（净化新星射程约9）
                        if disruptor.distance_to(enemy.position) > 9:
                            continue

                        # 检查是否已经被其他disruptor瞄准（缩短重复检查时间）
                        already_targeted = False
                        for target_pos, _ in self.disruptor_target_positions:
                            if enemy.position.distance_to(target_pos) < 2.5:  # 缩小重复范围
                                already_targeted = True
                                break

                        if already_targeted:
                            continue

                        # 检查友军安全距离（净化新星爆炸半径约1.5）
                        friendly_units_nearby = self.units.closer_than(3.0, enemy.position)  # 增加安全距离
                        if friendly_units_nearby.exists:
                            continue  # 跳过会伤害友军的位置

                        # 计算净化新星爆炸范围内的优先目标数量
                        nearby_priority_targets = priority_targets.closer_than(1.5, enemy.position)

                        # 重新设计价值评分 - 专注小型单位
                        value_score = 0
                        for nearby_enemy in nearby_priority_targets:
                            if nearby_enemy.type_id == UnitTypeId.MARINE:
                                value_score += 3  # Marine是主要目标
                            elif nearby_enemy.type_id == UnitTypeId.GHOST:
                                value_score += 4  # Ghost高价值目标
                            elif nearby_enemy.type_id == UnitTypeId.MARAUDER:
                                value_score += 3  # Marauder也是重要目标

                        # 检查是否在分配的扇形区域内（更宽松的角度分配）
                        angle_to_enemy = math.degrees(math.atan2(
                            enemy.position.y - disruptor.position.y,
                            enemy.position.x - disruptor.position.x
                        ))
                        angle_diff = abs(angle_to_enemy - sector_angle)
                        if angle_diff > 180:
                            angle_diff = 360 - angle_diff

                        # 如果在分配区域内且价值足够高（降低门槛让更多disruptor参与）
                        if (angle_diff <= 90 and value_score > max_damage_potential and
                            nearby_priority_targets.amount >= 1):  # 降低到1个目标就可以攻击
                            max_damage_potential = value_score
                            best_target_pos = enemy.position

                    # 如果没有在分配区域找到目标，寻找任何安全的优先目标
                    if not best_target_pos:
                        for enemy in priority_targets:
                            if disruptor.distance_to(enemy.position) > 9:
                                continue

                            # 检查友军安全
                            friendly_units_nearby = self.units.closer_than(2.5, enemy.position)
                            if friendly_units_nearby.exists:
                                continue

                            # 检查是否已被瞄准
                            already_targeted = False
                            for target_pos, _ in self.disruptor_target_positions:
                                if enemy.position.distance_to(target_pos) < 2.5:
                                    already_targeted = True
                                    break

                            if already_targeted:
                                continue

                            # 只要有优先目标就攻击
                            nearby_priority = priority_targets.closer_than(1.5, enemy.position).amount
                            if nearby_priority >= 1:
                                best_target_pos = enemy.position
                                break

                    if best_target_pos:
                        disruptor(AbilityId.EFFECT_PURIFICATIONNOVA, best_target_pos)
                        self.last_disruptor_time[disruptor.tag] = current_time
                        # 记录冷却时间
                        self.disruptor_cooldowns[disruptor.tag] = current_time
                        # 记录全局释放时间，确保下一个disruptor间隔1秒
                        self.last_global_disruptor_shot = current_time
                        # 记录目标位置，避免重复轰炸
                        self.disruptor_target_positions.append((best_target_pos, current_time))
                        continue

            # 技能不可用时，保持安全位置
            await self.position_disruptor_safely(disruptor)

    async def position_disruptor_safely(self, disruptor):
        """将disruptor定位到安全位置"""
        if not self.enemy_units.exists:
            return

        # 寻找优先目标来定位
        priority_targets = self.enemy_units.filter(lambda u: not u.is_flying and
                                                 (u.type_id == UnitTypeId.MARINE or
                                                  u.type_id == UnitTypeId.GHOST or
                                                  u.type_id == UnitTypeId.MARAUDER))

        if priority_targets.exists:
            closest_priority = priority_targets.closest_to(disruptor.position)
            ideal_distance = 7  # 理想距离：既能快速支援又保持安全
            current_distance = disruptor.distance_to(closest_priority)

            if current_distance < 4:
                # 太近了，后撤到理想距离
                safe_pos = disruptor.position.towards(closest_priority.position, -(4 - current_distance + 1))
                disruptor.move(safe_pos)
            elif current_distance > ideal_distance + 2:
                # 超过理想距离太多，主动靠近
                move_distance = min(4, current_distance - ideal_distance)
                move_pos = disruptor.position.towards(closest_priority.position, move_distance)
                disruptor.move(move_pos)
        else:
            # 没有优先目标时，主动靠近敌人但保持安全距离
            closest_enemy = self.enemy_units.closest_to(disruptor.position)
            ideal_distance = 7
            current_distance = disruptor.distance_to(closest_enemy)

            if current_distance < 4:
                # 太近了，后撤
                safe_pos = disruptor.position.towards(closest_enemy.position, -2)
                disruptor.move(safe_pos)
            elif current_distance > ideal_distance + 3:
                # 太远了，主动靠近到理想距离
                move_distance = min(4, current_distance - ideal_distance)
                move_pos = disruptor.position.towards(closest_enemy.position, move_distance)
                disruptor.move(move_pos)

    async def get_formation_position(self):
        """获取部队集结位置"""
        if self.units.exists:
            return self.units.center
        # 如果start_location为None，使用地图中心
        return Point2((self.game_info.map_size.x / 2, self.game_info.map_size.y / 2))

    async def should_engage(self):
        """根据兵种战力分数评估是否应该交战"""
        if not self.units.exists or not self.enemy_units.exists:
            return False

        # 战力分数表
        unit_values = {
            # Terran
            UnitTypeId.MARINE: 50,
            UnitTypeId.MARAUDER: 100,
            UnitTypeId.GHOST: 150,
            UnitTypeId.MEDIVAC: 120,
            UnitTypeId.SIEGETANK: 175,
            UnitTypeId.VIKINGFIGHTER: 125,
            UnitTypeId.LIBERATOR: 170,
            UnitTypeId.CYCLONE: 125,
            UnitTypeId.WIDOWMINE: 75,
            UnitTypeId.RAVEN: 200,
            UnitTypeId.THOR: 300,

            # Protoss
            UnitTypeId.ZEALOT: 75,
            UnitTypeId.STALKER: 125,
            UnitTypeId.COLOSSUS: 300,
            UnitTypeId.HIGHTEMPLAR: 150,
            UnitTypeId.DISRUPTOR: 250,
            UnitTypeId.SENTRY: 75,
            UnitTypeId.DARKTEMPLAR: 175,
            UnitTypeId.TEMPEST: 300,
            UnitTypeId.CARRIER: 400,
        }

        our_army_value = sum(unit_values.get(u.type_id, 100) for u in self.units)
        enemy_army_value = sum(unit_values.get(u.type_id, 100) for u in self.enemy_units)
        
        # 如果战力 ≥ 敌人 80%，则可以交战
        return our_army_value >= enemy_army_value * 0.8

    async def control_purification_novas(self):
        """控制净化新星球的移动，避免友军伤害"""
        # 获取所有净化新星球
        purification_novas = self.units.filter(lambda u: u.name == "PurificationNova")

        for nova in purification_novas:
            # 检查新星球周围是否有友军
            friendly_units_nearby = self.units.closer_than(3.0, nova.position)
            if friendly_units_nearby.exists:
                # 有友军，将新星球移动到安全位置
                if self.enemy_units.exists:
                    # 寻找最近的敌人群
                    enemy_ground = self.enemy_units.filter(lambda u: not u.is_flying)
                    if enemy_ground.exists:
                        # 找到没有友军的敌人位置
                        for enemy in enemy_ground:
                            nearby_friendlies = self.units.closer_than(3.0, enemy.position)
                            if not nearby_friendlies.exists:
                                # 移动新星球到这个安全的敌人位置
                                nova.move(enemy.position)
                                break




def main():
    # 可运行flat_test_final,flat_test_2_final,flat_test_3_final
    try:
        run_game(maps.get("test1"), [Human(Race.Terran, fullscreen=True), Bot(Race.Protoss, ProtossBot(), fullscreen=False)], realtime=True)
    except Exception as e:
        print(f"Game ended with exception: {e}")
        # 游戏可能正常结束，只是结果处理有问题
        pass


if __name__ == "__main__":
    main()