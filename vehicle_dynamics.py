"""
Boyuna Araç Dinamiği ve Güç Aktarım (Motor/İnvertör) Modülü

Bu modül, aracın anlık hız (v), ivme (a) ve yol eğiminden (theta) hareketle:
1. Tekerleğe etkiyen yuvarlanma, hava, eğim ve eylemsizlik kuvvetlerini hesaplar.
2. Mekanik tekerlek gücünü ve motor elektriksel güç talebini bulur.
3. Çekiş ve rejeneratif frenleme anındaki motor/invertör atık ısı üretimini hesaplar.
4. Motorun saniye saniye ısıl durumunu ve soğutma sıvısına aktardığı atık ısıyı modeller.
"""

from dataclasses import dataclass
import numpy as np
from config import VehicleDynamicsConfig, PowertrainThermalConfig


@dataclass
class VehicleDynamicsStepResult:
    """Tek bir zaman adımı için araç dinamiği ve motor ısıl çıktıları."""
    # Kuvvetler (Newton)
    f_roll_n: float
    f_aero_n: float
    f_grade_n: float
    f_accel_n: float
    f_total_n: float
    
    # Güçler (Watt)
    p_wheel_w: float                    # Tekerlek mekanik gücü (+ çekiş, - frenleme)
    p_motor_elec_w: float               # Motorun bataryadan çektiği (+ deşarj) veya bastığı (- rejen şarj) elektriksel güç
    p_regen_elec_w: float               # Rejenerasyon ile geri kazanılan elektrik gücü (W)
    p_total_battery_demand_w: float     # Motor + Temel yardımcı yükler (W)
    
    # Isı Üretimi ve Sıcaklık
    q_motor_heat_gen_w: float           # Motor ve invertörde verimsizlikten açığa çıkan anlık atık ısı (W)
    q_motor_to_coolant_w: float         # Motordan soğutma sıvısına geçen ısı (W)
    motor_temp_c: float                 # Anlık motor/invertör sıcaklığı (°C)


class VehicleDynamics:
    """Boyuna araç dinamiği ve elektrik motoru elektro-termal modeli."""

    def __init__(self, dynamics_cfg: VehicleDynamicsConfig, powertrain_cfg: PowertrainThermalConfig, initial_motor_temp_c: float = 25.0):
        self.dyn_cfg = dynamics_cfg
        self.pwt_cfg = powertrain_cfg
        
        # Dönen kütle eylemsizliği dahil efektif araç kütlesi
        self.effective_mass_kg = self.dyn_cfg.mass_kg * self.dyn_cfg.rotational_mass_factor
        
        # Motorun başlangıç sıcaklığı (°C)
        self.motor_temp_c = float(initial_motor_temp_c)

    def step(self, v_mps: float, a_mps2: float, grade_rad: float = 0.0, coolant_in_temp_c: float = 25.0, ambient_temp_c: float = 20.0, dt: float = 1.0) -> VehicleDynamicsStepResult:
        """
        Anlık sürüş parametrelerine göre bir zaman adımı (dt) ilerletir.
        
        Parametreler:
        - v_mps: Araç hızı (m/s)
        - a_mps2: Araç ivmesi (m/s^2)
        - grade_rad: Yol eğimi açısı (radyan)
        - coolant_in_temp_c: Motora giren soğutma sıvısı sıcaklığı (°C)
        - ambient_temp_c: Dış ortam hava sıcaklığı (°C)
        - dt: Zaman adımı (saniye)
        """
        # 1. Direnç Kuvvetleri (Newton)
        # Yuvarlanma direnci: Araç dururken (v ~ 0) sıfırdır
        if v_mps > 0.05:
            f_roll = self.dyn_cfg.crr * self.dyn_cfg.mass_kg * self.dyn_cfg.gravity_m_s2 * np.cos(grade_rad)
        else:
            f_roll = 0.0

        # Aerodinamik sürtünme: 0.5 * rho * Cd * A * v^2
        f_aero = 0.5 * self.dyn_cfg.air_density_kg_m3 * self.dyn_cfg.cd * self.dyn_cfg.frontal_area_m2 * (v_mps ** 2)

        # Yerçekimi eğim kuvveti: m * g * sin(theta)
        f_grade = self.dyn_cfg.mass_kg * self.dyn_cfg.gravity_m_s2 * np.sin(grade_rad)

        # Eylemsizlik (Hızlanma / Yavaşlama) kuvveti: m_eff * a
        f_accel = self.effective_mass_kg * a_mps2

        # Toplam çekiş kuvveti
        f_total = f_roll + f_aero + f_grade + f_accel

        # 2. Tekerlek Mekanik Gücü: P = F * v (Watt)
        p_wheel = f_total * v_mps

        # 3. Motor Elektriksel Gücü ve Atık Isı Üretimi
        max_trac_w = self.dyn_cfg.max_traction_power_kw * 1000.0
        max_regen_w = self.dyn_cfg.max_regen_power_kw * 1000.0

        if p_wheel >= 0.0:
            # Çekiş (Traction) Modu: Bataryadan motora güç çekilir
            p_wheel_clamped = min(p_wheel, max_trac_w)
            p_motor_elec = p_wheel_clamped / self.dyn_cfg.drivetrain_efficiency
            p_regen_elec = 0.0
            # Motorda açığa çıkan atık ısı (verimsizlik payı)
            q_motor_heat_gen = p_wheel_clamped * (1.0 - self.dyn_cfg.drivetrain_efficiency)
        else:
            # Rejeneratif Frenleme Modu: Tekerlekten motora ve bataryaya enerji akar
            p_braking_mech = abs(p_wheel)
            # Rejenerasyon sınırları (maksimum rejen gücü sınırı)
            p_regen_mech = min(p_braking_mech, max_regen_w)
            p_regen_elec = p_regen_mech * self.dyn_cfg.regen_efficiency
            p_motor_elec = -p_regen_elec # Negatif = bataryayı şarj eder
            # Rejen anında motor ve invertörde oluşan atık ısı
            q_motor_heat_gen = p_regen_mech * (1.0 - self.dyn_cfg.regen_efficiency)

        # Toplam batarya güç talebi (Motor + 12V yardımcı sistemler)
        p_total_battery_demand = p_motor_elec + self.dyn_cfg.base_auxiliary_power_w

        # 4. Motor Isıl Dengesi (Thermal Balance)
        # Motordan soğutma sıvısına geçen ısı (W)
        delta_t_coolant = self.motor_temp_c - coolant_in_temp_c
        q_motor_to_coolant = max(0.0, self.pwt_cfg.coolant_coupling_ua_w_k * delta_t_coolant)

        # Motor gövdesinden kaput altına doğal ısı kaybı (W)
        delta_t_ambient = self.motor_temp_c - ambient_temp_c
        q_motor_to_ambient = self.pwt_cfg.ambient_loss_ua_w_k * delta_t_ambient

        # Diferansiyel Denklem: dT/dt = (Q_in - Q_coolant - Q_ambient) / C_th
        net_q_motor = q_motor_heat_gen - q_motor_to_coolant - q_motor_to_ambient
        d_temp_dt = net_q_motor / self.pwt_cfg.thermal_capacitance_j_k
        self.motor_temp_c += d_temp_dt * dt

        return VehicleDynamicsStepResult(
            f_roll_n=float(f_roll),
            f_aero_n=float(f_aero),
            f_grade_n=float(f_grade),
            f_accel_n=float(f_accel),
            f_total_n=float(f_total),
            p_wheel_w=float(p_wheel),
            p_motor_elec_w=float(p_motor_elec),
            p_regen_elec_w=float(p_regen_elec),
            p_total_battery_demand_w=float(p_total_battery_demand),
            q_motor_heat_gen_w=float(q_motor_heat_gen),
            q_motor_to_coolant_w=float(q_motor_to_coolant),
            motor_temp_c=float(self.motor_temp_c)
        )


if __name__ == "__main__":
    from config import DEFAULT_VEHICLE
    vd = VehicleDynamics(DEFAULT_VEHICLE.dynamics, DEFAULT_VEHICLE.powertrain, initial_motor_temp_c=25.0)
    
    print("=" * 65)
    print("  ARAÇ DİNAMİĞİ VE MOTOR GÜÇ/ISI MODELİ TESTİ")
    print("=" * 65)
    
    # Test Senaryosu: 100 km/h (27.78 m/s) sabit hız, 0 ivme, %0 eğim
    v_test = 100.0 / 3.6
    res = vd.step(v_mps=v_test, a_mps2=0.0, grade_rad=0.0, dt=1.0)
    print(f"100 km/h Sabit Hızda:")
    print(f"  • Toplam Direnç Kuvveti : {res.f_total_n:.1f} N (Hava: {res.f_aero_n:.1f} N, Yuvarlanma: {res.f_roll_n:.1f} N)")
    print(f"  • Tekerlek Gücü         : {res.p_wheel_w / 1000.0:.2f} kW")
    print(f"  • Bataryadan Çekilen Güç: {res.p_total_battery_demand_w / 1000.0:.2f} kW (Motor: {res.p_motor_elec_w / 1000.0:.2f} kW)")
    print(f"  • Motor Atık Isısı      : {res.q_motor_heat_gen_w:.1f} W")
    
    # Test Senaryosu 2: Sert Hızlanma (0 -> 100 km/h, a = 3.0 m/s^2)
    res_acc = vd.step(v_mps=15.0, a_mps2=3.0, grade_rad=0.0, dt=1.0)
    print(f"\nSert Hızlanma Anında (54 km/h, a = 3.0 m/s²):")
    print(f"  • Tekerlek Gücü         : {res_acc.p_wheel_w / 1000.0:.2f} kW")
    print(f"  • Bataryadan Çekilen Güç: {res_acc.p_total_battery_demand_w / 1000.0:.2f} kW")
    print(f"  • Motor Atık Isısı      : {res_acc.q_motor_heat_gen_w:.1f} W (Kabin ısıtmada kullanılabilir!)")
    print("=" * 65)
