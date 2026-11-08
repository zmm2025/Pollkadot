"""Compare races.csv against well-known certified statewide results (values typed from memory of
official canvasses; used only as a >0.5% sanity check)."""
import pandas as pd
R = 'data/results'
r = pd.read_csv(f'{R}/races.csv', keep_default_na=False)
K = [  # year, office, special, state, D votes (top D cand), R votes (top R cand)
    (2018, 'SEN', 0, 'TX', 4045632, 4260553), (2018, 'SEN', 0, 'FL', 4089472, 4099505),
    (2018, 'GOV', 0, 'FL', 4043723, 4076186), (2018, 'GOV', 0, 'GA', 1923685, 1978408),
    (2018, 'SEN', 0, 'AZ', 1191100, 1135200), (2018, 'SEN', 0, 'NV', 490071, 441202),
    (2018, 'SEN', 0, 'MO', 1112935, 1254927), (2018, 'SEN', 0, 'IN', 1023553, 1158000),
    (2018, 'GOV', 0, 'OH', 2067847, 2231917), (2018, 'SEN', 0, 'WI', 1472914, 1184885),
    (2018, 'GOV', 0, 'WI', 1324307, 1295080), (2018, 'SEN', 1, 'MN', 1370540, 1095777),
    (2018, 'SEN', 1, 'MS', 386742, 389995), (2018, 'GOV', 0, 'NY', 3635340, 2207602),
    (2018, 'GOV', 0, 'PA', 2895652, 2039882), (2018, 'GOV', 0, 'MI', 2266193, 1859534),
    (2020, 'SEN', 0, 'GA', 2374519, 2462617), (2020, 'SEN', 1, 'GA', 1617035, 1273214),
    (2020, 'SEN', 1, 'AZ', 1716467, 1637661), (2020, 'SEN', 0, 'NC', 2569965, 2665598),
    (2020, 'GOV', 0, 'NC', 2834790, 2586605), (2020, 'SEN', 0, 'MI', 2734568, 2642233),
    (2020, 'SEN', 0, 'ME', 347223, 417645), (2020, 'SEN', 0, 'TX', 4888764, 5962983),
    (2020, 'PRES', 0, 'GA', 2473633, 2461854), (2020, 'PRES', 0, 'PA', 3458229, 3377674),
    (2022, 'SEN', 0, 'GA', 1946117, 1908442), (2022, 'SEN', 2, 'GA', 1820633, 1721244),
    (2022, 'SEN', 0, 'PA', 2751012, 2487260), (2022, 'SEN', 0, 'AZ', 1322027, 1196308),
    (2022, 'SEN', 0, 'NV', 498316, 490388), (2022, 'SEN', 0, 'OH', 1939489, 2192114),
    (2022, 'SEN', 0, 'WI', 1310467, 1337185), (2022, 'SEN', 0, 'NC', 1784049, 1905786),
    (2022, 'GOV', 0, 'FL', 3106313, 4614210), (2022, 'GOV', 0, 'NY', 3140415, 2762581),
    (2022, 'GOV', 0, 'TX', 3553656, 4437099), (2022, 'GOV', 0, 'AZ', 1287891, 1270774),
    (2022, 'GOV', 0, 'MI', 2430505, 1960635), (2022, 'GOV', 0, 'PA', 3031137, 2238477),
    (2022, 'SEN', 1, 'OK', 405389, 710643), (2022, 'SEN', 0, 'CA', 6621616, 4222025),
    (2022, 'GOV', 0, 'SC', 692691, 988501), (2022, 'SEN', 0, 'SC', 627616, 1066274),
    (2024, "SEN", 0, "TX", 5031249, 5990741), (2024, 'SEN', 0, 'PA', 3384180, 3399295),
    (2016, 'SEN', 0, 'PA', 2865012, 2951702), (2016, 'SEN', 0, 'WI', 1380335, 1479471),
    (2016, 'PRES', 0, 'MI', 2268839, 2279543), (2016, 'GOV', 0, 'IN', 1235503, 1397396),
    (2016, 'SEN', 0, 'IN', 1158947, 1423991), (2016, 'GOV', 0, 'NC', 2309157, 2298880),
    (2016, 'GOV', 0, 'MO', 1277360, 1433397), (2016, 'SEN', 0, 'NH', 354649, 353632),
    (2016, 'SEN', 0, 'NV', 521994, 495079), (2016, 'GOV', 0, 'NH', 337589, 354040), (2016, 'PRES', 0, 'FL', 4504975, 4617886),
]
rows = []
for y, o, sp, st, dv, rv in K:
    m = r[(r.year == y) & (r.office == o) & (r.special == sp) & (r.state_po == st)]
    if m.empty:
        rows.append((y, o, sp, st, dv, None, rv, None, None, None, 'MISSING'))
        continue
    m = m.iloc[0]
    dd = (m.dem_cand_votes / dv - 1) * 100
    rd = (m.rep_cand_votes / rv - 1) * 100
    rows.append((y, o, sp, st, dv, m.dem_cand_votes, rv, m.rep_cand_votes, round(dd, 2), round(rd, 2),
                 'OK' if abs(dd) <= 0.5 and abs(rd) <= 0.5 else 'DEVIATES'))
out = pd.DataFrame(rows, columns=['year', 'office', 'special', 'state', 'D_known', 'D_ours', 'R_known', 'R_ours',
                                  'dD_pct', 'dR_pct', 'status'])
pd.set_option('display.width', 200)
print(out.to_string())
out.to_csv('data/work/known_check.csv', index=False)
