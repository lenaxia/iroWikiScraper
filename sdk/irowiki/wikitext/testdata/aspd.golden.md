<!--template:expert-->
# Overview
Attack Speed is abbreviated as ASPD. It depends on the player's [class](wiki:Classes), equipped [Weapon](wiki:Weapons) Type, Speed Modifiers, [AGI](wiki:AGI) and [DEX](wiki:DEX).
## Factors affecting Attack Speed
- The player's class.
- The player's weapon type.
- Increasing [AGI](wiki:Stats) to gain higher Attack Speed. ([DEX](wiki:Stats) provides negligible Attack Speed increases)
- Wearing a [shield](wiki:shield) decreases Attack Speed. The difference varies by class and is more dramatic at higher base Attack Speeds.
- Some items, skills and equipments can either increase or decrease Attack Speed.

# ASPD Formula
Each class has a Base ASPD (146 ~ 158) which is affected by the weapon (-50 ~ +2). Equipping a [shield](wiki:shield) reduces ASPD by 5 ~ 10.
**ASPD Penalty** = [ 1 − { *Job Base ASPD* − 144 } ÷ 50 ]
  *Note*: Limit down to a maximum of 0.96. Keep 2 decimals.
**ASPD Correction** = [ { &radic;( 205 ) − &radic;( [AGI](wiki:Stats) ) } ÷ 7.15 ]
  *Note*: Round up to 3 decimals.
**Equip ASPD %** = [ { 195 − *Base ASPD* } × *Total of [Equip ASPD Mod](wiki:ASPD)* ]
  *Note*: Round down to 1 decimal.
**Base ASPD** = [ 200 − { 200 − ( *Job Base ASPD* + *Shield Penalty* − *ASPD Correction* + &radic;[ [AGI](wiki:Stats) × 9.999 + [DEX](wiki:Stats) × 0.19212 ] × *Aspd Penalty* ) } × { 1 − *[Potion ASPD Mod](wiki:ASPD)* − *[Skill ASPD Mod](wiki:ASPD)* } ]
  *Note*: Round down to 2 decimal.
**Final ASPD** = [ *Base ASPD* + { *Equip ASPD %* } + *Equip ASPD Fixed* ]
## Links
- [ASPD Tables (xls)](http://kaitch.com/files/FJK_iRO_ASPD_Calc_1.11.xls)
- <http://j.mp/iROASPDCalc>
# Speed Modifiers
*Note*: Non-percentage numbers are **absolute modifiers**. These ones are directly added to the ASPD at the end of the calculations.
The following items will affect ASPD:
## Potion ASPD Modifiers
  *Main article: [ASPD Potion](wiki:ASPD_Potion).*
Only the potion with greater effect will be put into consideration, they never stack to each other.
| --- | --- | --- |
| Consumable Potions | Modifier | Additional notes |
|  |  |  |