from sc2 import maps
from sc2.data import Race
from sc2.main import run_game
from sc2.player import Bot, Human
from sc2.bot_ai import BotAI
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.position import Point2

class EnhancedZergBot(BotAI):
    def __init__(self):
        super().__init__()
        self.target_position = Point2((2.0, 2.0))
        self.attack_duration = 100
        self.threat_priority = {
            UnitTypeId.GHOST: 10,
            UnitTypeId.BATTLECRUISER: 10,
            UnitTypeId.THOR: 9,
            UnitTypeId.THORAP: 9,
            UnitTypeId.SIEGETANKSIEGED: 9,
            UnitTypeId.SIEGETANK: 8,
            UnitTypeId.MEDIVAC: 8,
            UnitTypeId.BANSHEE: 8,
            UnitTypeId.LIBERATOR: 8,
            UnitTypeId.RAVEN: 8,
            UnitTypeId.VIKINGFIGHTER: 7,
            UnitTypeId.HELLIONTANK: 7,
            UnitTypeId.MARAUDER: 6,
            UnitTypeId.HELLION: 6,
            UnitTypeId.MARINE: 5,
            UnitTypeId.REAPER: 5,
            UnitTypeId.SCV: 4
        }

    async def on_step(self, iteration: int):
        if iteration == 0:
            print("Enhanced ZVT Micro Bot initialized!")
            print("Our units: Zergling, Baneling, Roach, Hydralisk, Lurker, Corruptor, Infestor, Viper, Overseer, Queen, Broodlord")

        await self.enhanced_micro_management(iteration)

    async def enhanced_micro_management(self, iteration: int):
        if not self.units.exists:
            return

        if iteration < self.attack_duration:
            await self.broodlord_control()
            await self.hydralisk_support()
            await self.zergling_control()
            await self.roach_control()
            await self.lurker_control()
            await self.corruptor_control()
            await self.queen_support()
        else:
            await self.cleanup_survivors()

        await self.enhanced_infestor_control()
        await self.enhanced_viper_control()
        await self.overseer_control()

    async def broodlord_control(self):
        broodlords = self.units(UnitTypeId.BROODLORD)
        for broodlord in broodlords:
            if self.enemy_units.exists:
                ground_targets = self.enemy_units.filter(lambda u: not u.is_flying)
                if ground_targets.exists:
                    in_range = ground_targets.filter(lambda u: broodlord.distance_to(u) <= 10)
                    if in_range.exists:
                        target = self.select_priority_target(in_range, broodlord.position)
                        broodlord.attack(target)
                    else:
                        closest = ground_targets.closest_to(broodlord.position)
                        move_pos = broodlord.position.towards(closest.position, 3)
                        broodlord.move(move_pos)
                else:
                    broodlord.attack(self.target_position)

    async def hydralisk_support(self):
        hydras = self.units(UnitTypeId.HYDRALISK)
        for hydra in hydras:
            air = self.enemy_units.filter(lambda u: u.is_flying)
            if air.exists:
                hydra.attack(air.closest_to(hydra.position))
            else:
                ground = self.enemy_units.filter(lambda u: not u.is_flying)
                if ground.exists:
                    target = self.select_priority_target(ground, hydra.position)
                    hydra.attack(target)

    async def zergling_control(self):
        zerglings = self.units(UnitTypeId.ZERGLING)
        banelings = self.units(UnitTypeId.BANELING)
        for z in zerglings:
            if self.enemy_units.exists:
                bio = self.enemy_units.filter(lambda u: not u.is_flying and u.type_id in [UnitTypeId.MARINE, UnitTypeId.MARAUDER, UnitTypeId.GHOST])
                if bio.exists:
                    z.attack(bio.closest_to(z.position))
                else:
                    ground = self.enemy_units.filter(lambda u: not u.is_flying)
                    if ground.exists:
                        z.attack(ground.closest_to(z.position))
        for b in banelings:
            if self.enemy_units.exists:
                ground = self.enemy_units.filter(lambda u: not u.is_flying)
                if ground.exists:
                    b.attack(ground.closest_to(b.position))

    async def roach_control(self):
        roaches = self.units(UnitTypeId.ROACH)
        for roach in roaches:
            if self.enemy_units.exists:
                roach.attack(self.enemy_units.closest_to(roach.position))

    async def lurker_control(self):
        lurkers = self.units(UnitTypeId.LURKERMP)
        for lurker in lurkers:
            if not lurker.is_burrowed:
                lurker(AbilityId.BURROWDOWN_LURKER)
            else:
                if self.enemy_units.exists:
                    target = self.select_priority_target(self.enemy_units, lurker.position)
                    lurker.attack(target)

    async def corruptor_control(self):
        corruptors = self.units(UnitTypeId.CORRUPTOR)
        for c in corruptors:
            air = self.enemy_units.filter(lambda u: u.is_flying)
            if air.exists:
                target = self.select_priority_target(air, c.position)
                c.attack(target)

    async def queen_support(self):
        queens = self.units(UnitTypeId.QUEEN)
        for q in queens:
            wounded = self.units.filter(lambda u: u.health_percentage < 0.5)
            if wounded.exists and q.energy >= 50:
                target = wounded.closest_to(q.position)
                abilities = await self.get_available_abilities(q)
                if AbilityId.EFFECT_TRANSFUSION in abilities:
                    q(AbilityId.EFFECT_TRANSFUSION, target)
                    continue
            if self.enemy_units.exists:
                q.attack(self.enemy_units.closest_to(q.position))

    async def overseer_control(self):
        overseers = self.units(UnitTypeId.OVERSEER)
        if overseers.exists and self.units.exists:
            center = self.units.center
            for o in overseers:
                if o.distance_to(center) > 5:
                    o.move(center)

    async def cleanup_survivors(self):
        combat_units = self.units.filter(lambda u: u.type_id in [
            UnitTypeId.ROACH, UnitTypeId.HYDRALISK, UnitTypeId.ZERGLING, 
            UnitTypeId.BANELING, UnitTypeId.BROODLORD, UnitTypeId.CORRUPTOR, 
            UnitTypeId.LURKERMP, UnitTypeId.QUEEN
        ])
        for unit in combat_units:
            if self.enemy_units.exists:
                unit.attack(self.enemy_units.closest_to(unit.position))

    def select_priority_target(self, enemy_units, from_position):
        if not enemy_units.exists:
            return None
        best_target, best_score = None, -1
        for e in enemy_units:
            threat = self.threat_priority.get(e.type_id, 3)
            dist = from_position.distance_to(e.position)
            dist_score = max(0, 15 - dist) / 15
            health_factor = 1.5 if e.health_percentage < 0.3 else 1.0
            score = threat * (1 + dist_score) * health_factor
            if score > best_score:
                best_score, best_target = score, e
        return best_target

    async def enhanced_infestor_control(self):
        infestors = self.units(UnitTypeId.INFESTOR)
        for inf in infestors:
            if inf.energy >= 75:
                ghosts = self.enemy_units.filter(lambda u: u.type_id == UnitTypeId.GHOST)
                if ghosts.exists:
                    target = ghosts.closest_to(inf.position)
                    abilities = await self.get_available_abilities(inf)
                    if AbilityId.FUNGALGROWTH_FUNGALGROWTH in abilities:
                        inf(AbilityId.FUNGALGROWTH_FUNGALGROWTH, target.position)
            if inf.energy >= 100:
                thors = self.enemy_units.filter(lambda u: u.type_id in [UnitTypeId.THOR, UnitTypeId.THORAP])
                if thors.exists:
                    target = thors.closest_to(inf.position)
                    abilities = await self.get_available_abilities(inf)
                    if AbilityId.NEURALPARASITE_NEURALPARASITE in abilities:
                        inf(AbilityId.NEURALPARASITE_NEURALPARASITE, target)

    async def enhanced_viper_control(self):
        vipers = self.units(UnitTypeId.VIPER)
        for v in vipers:
            if v.energy >= 100:
                thors = self.enemy_units.filter(lambda u: u.type_id in [UnitTypeId.THOR, UnitTypeId.THORAP])
                if thors.exists:
                    target = thors.closest_to(v.position)
                    abilities = await self.get_available_abilities(v)
                    if AbilityId.BLINDINGCLOUD_BLINDINGCLOUD in abilities:
                        v(AbilityId.BLINDINGCLOUD_BLINDINGCLOUD, target.position)
            if v.energy >= 75:
                abduct_targets = self.enemy_units.filter(lambda u: u.type_id in [UnitTypeId.GHOST, UnitTypeId.MEDIVAC, UnitTypeId.SIEGETANKSIEGED])
                if abduct_targets.exists:
                    target = abduct_targets.closest_to(v.position)
                    abilities = await self.get_available_abilities(v)
                    if AbilityId.EFFECT_ABDUCT in abilities:
                        v(AbilityId.EFFECT_ABDUCT, target)

def main():
    run_game(
        maps.get("test1"),
        [
            Human(Race.Terran, fullscreen=True),
            Bot(Race.Zerg, EnhancedZergBot(), fullscreen=False)
        ],
        realtime=True
    )

if __name__ == "__main__":
    main()
