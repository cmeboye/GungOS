"""Compact unit tables, expanded only for the selected quantity.

Each row is symbol|name|SI multiplier[|SI offset]. A negative multiplier
denotes a reciprocal fuel-economy unit. Names distinguish customary systems.
Definitions and factors: NIST SP 811 Appendix B; see guides/UnitConverter.md.
"""

# id, label, family, SI symbol, rows, note
CATEGORIES = (
('length', 'Length', 'Everyday', 'm', '''m|Metre meter|1
mm|Millimetre|.001
cm|Centimetre|.01
km|Kilometre|1000
um|Micrometre micron|1e-6
nm|Nanometre|1e-9
in|Inch|.0254
ft|Foot feet|.3048
yd|Yard|.9144
mi|Mile|1609.344
nmi|Nautical mile|1852
mil|Thousandth inch thou|.0000254
au|Astronomical unit|149597870700
ly|Light year (Julian)|9460730472580800''', 'International inch and foot; nautical mile = 1852 m.'),
('mass', 'Mass', 'Everyday', 'kg', '''kg|Kilogram|1
g|Gram|.001
mg|Milligram|1e-6
ug|Microgram|1e-9
t|Metric tonne|1000
lb|Pound avoirdupois|.45359237
oz|Ounce avoirdupois|.028349523125
st|Stone|6.35029318
ton-US|US short ton|907.18474
ton-UK|Imperial long ton|1016.0469088
ct|Metric carat|.0002
gr|Grain|.00006479891
ozt|Troy ounce|.0311034768
slug|Slug|14.5939029372''', 'Mass, not force. Pound = 0.45359237 kg.'),
('area', 'Area', 'Everyday', 'm2', '''m2|Square metre|1
mm2|Square millimetre|1e-6
cm2|Square centimetre|.0001
km2|Square kilometre|1e6
ha|Hectare|10000
acre|International acre|4046.8564224
in2|Square inch|.00064516
ft2|Square foot|.09290304
yd2|Square yard|.83612736
mi2|Square mile|2589988.110336''', 'Area factors include the square of the length scale.'),
('volume', 'Volume / cooking', 'Everyday', 'm3', '''m3|Cubic metre|1
L|Litre liter|.001
mL|Millilitre|1e-6
cm3|Cubic centimetre cc|1e-6
mm3|Cubic millimetre|1e-9
in3|Cubic inch|.000016387064
ft3|Cubic foot|.028316846592
yd3|Cubic yard|.764554857984
gal-US|US liquid gallon|.003785411784
gal-UK|Imperial gallon|.00454609
qt-US|US liquid quart|.000946352946
pt-US|US liquid pint|.000473176473
pt-UK|Imperial pint|.00056826125
floz-US|US fluid ounce|.0000295735295625
floz-UK|Imperial fluid ounce|.0000284130625
cup-US|US customary cup|.0002365882365
cup-metric|Metric cup (250 mL)|.00025
tbsp-US|US tablespoon|.00001478676478125
tsp-US|US teaspoon|.00000492892159375
bbl|Petroleum barrel (42 US gal)|.158987294928
bu-US|US dry bushel|.03523907016688''', 'US liquid, US dry and Imperial measures differ.'),
('temperature', 'Temperature', 'Everyday', 'K', '''K|Kelvin|1
degC|Celsius centigrade|1|273.15
degF|Fahrenheit|.555555555555556|255.372222222222
degR|Rankine|.555555555555556''', 'Absolute temperatures; values below absolute zero are rejected.'),
('interval', 'Temperature interval', 'Thermal', 'K', '''K|Kelvin difference|1
degC|Celsius difference|1
degF|Fahrenheit difference|.555555555555556
degR|Rankine difference|.555555555555556''', 'Differences only: no temperature offsets.'),
('time', 'Time', 'Everyday', 's', '''s|Second|1
ms|Millisecond|.001
us|Microsecond|1e-6
ns|Nanosecond|1e-9
min|Minute|60
h|Hour|3600
d|Day|86400
wk|Week|604800
yr|Julian year (365.25 days)|31557600''', 'Year means 365.25 days; calendar months have no fixed duration.'),
('speed', 'Speed', 'Everyday', 'm/s', '''m/s|Metre per second|1
km/h|Kilometre per hour kph|.277777777777778
mph|Mile per hour|.44704
ft/s|Foot per second|.3048
kn|Knot|.514444444444444
cm/s|Centimetre per second|.01
m/min|Metre per minute|.0166666666666667''', 'Mach depends on the medium and is not a fixed speed unit.'),
('angle', 'Angle', 'Everyday', 'rad', '''rad|Radian|1
deg|Degree|.0174532925199433
rev|Revolution turn|6.28318530717959
grad|Gradian gon|.015707963267949
arcmin|Arcminute|.000290888208665722
arcsec|Arcsecond|.00000484813681109536''', ''),
('pressure', 'Pressure / stress', 'Engineering', 'Pa', '''Pa|Pascal|1
kPa|Kilopascal|1000
MPa|Megapascal|1e6
GPa|Gigapascal|1e9
bar|Bar|100000
mbar|Millibar|100
atm|Standard atmosphere|101325
psi|Pound force per square inch|6894.75729316836
ksi|Thousand psi|6894757.29316836
psf|Pound force per square foot|47.8802589803358
Torr|Torr (1/760 atm)|133.322368421053
mmHg|Conventional millimetre mercury|133.322387415
inHg|Conventional inch mercury|3386.388640341
mmH2O|Conventional millimetre water|9.80665
inH2O|Conventional inch water|249.08891''', 'No gauge/absolute offset is assumed. Water/mercury columns are conventional.'),
('force', 'Force', 'Engineering', 'N', '''N|Newton|1
kN|Kilonewton|1000
MN|Meganewton|1e6
mN|Millinewton|.001
dyn|Dyne|.00001
kgf|Kilogram force|9.80665
lbf|Pound force|4.4482216152605
kip|Thousand pound force|4448.2216152605''', 'Force units use standard gravity 9.80665 m/s2.'),
('energy', 'Energy / work / heat', 'Engineering', 'J', '''J|Joule|1
kJ|Kilojoule|1000
MJ|Megajoule|1e6
Wh|Watt hour|3600
kWh|Kilowatt hour|3600000
cal-th|Thermochemical calorie|4.184
kcal-th|Thermochemical kilocalorie food|4184
cal-IT|International table calorie|4.1868
Btu-IT|International table BTU|1055.05585262
ft-lbf|Foot pound force|1.3558179483314
eV|Electronvolt|1.602176634e-19
erg|Erg|1e-7''', 'Calorie and BTU conventions are labelled explicitly.'),
('power', 'Power', 'Engineering', 'W', '''W|Watt|1
mW|Milliwatt|.001
kW|Kilowatt|1000
MW|Megawatt|1e6
hp|Mechanical horsepower|745.69987158227
PS|Metric horsepower|735.49875
Btu-IT/h|BTU IT per hour|.293071070172222
TR|Refrigeration ton (12000 BTU/h)|3516.85284206667
ft-lbf/s|Foot pound force per second|1.3558179483314''', 'Mechanical hp and metric PS are different.'),
('torque', 'Torque / moment of force', 'Engineering', 'N*m', '''N*m|Newton metre|1
N*mm|Newton millimetre|.001
kN*m|Kilonewton metre|1000
lbf*ft|Pound force foot|1.3558179483314
lbf*in|Pound force inch|.112984829027617
kgf*m|Kilogram force metre|9.80665
ozf*in|Ounce force inch|.00706155181422604''', 'Torque and energy share dimensions but describe different quantities.'),
('acceleration', 'Acceleration', 'Engineering', 'm/s2', '''m/s2|Metre per second squared|1
ft/s2|Foot per second squared|.3048
cm/s2|Centimetre per second squared Gal|.01
g0|Standard gravity|9.80665
in/s2|Inch per second squared|.0254''', ''),
('angular', 'Angular velocity', 'Engineering', 'rad/s', '''rad/s|Radian per second|1
deg/s|Degree per second|.0174532925199433
rpm|Revolution per minute|.10471975511966
rev/s|Revolution per second|6.28318530717959''', ''),
('frequency', 'Frequency', 'Engineering', 'Hz', '''Hz|Hertz|1
mHz|Millihertz|.001
kHz|Kilohertz|1000
MHz|Megahertz|1e6
GHz|Gigahertz|1e9
1/min|Cycles per minute|.0166666666666667''', 'Cycles per second, not radians per second.'),
('density', 'Density', 'Engineering', 'kg/m3', '''kg/m3|Kilogram per cubic metre|1
g/cm3|Gram per cubic centimetre|1000
g/mL|Gram per millilitre|1000
kg/L|Kilogram per litre|1000
lb/ft3|Pound per cubic foot|16.01846337396
lb/in3|Pound per cubic inch|27679.9047102
lb/gal-US|Pound per US gallon|119.826427316897
lb/gal-UK|Pound per Imperial gallon|99.7763726631016''', ''),
('specific-volume', 'Specific volume', 'Engineering', 'm3/kg', '''m3/kg|Cubic metre per kilogram|1
L/kg|Litre per kilogram|.001
cm3/g|Cubic centimetre per gram|.001
ft3/lb|Cubic foot per pound|.0624279605761446''', ''),
('area-inertia', 'Second moment of area', 'Engineering', 'm4', '''m4|Metre to fourth power|1
cm4|Centimetre to fourth power|1e-8
mm4|Millimetre to fourth power|1e-12
in4|Inch to fourth power|4.162314256e-7
ft4|Foot to fourth power|.0086309748412416''', 'Section property I; distinct from mass moment of inertia.'),
('mass-inertia', 'Mass moment of inertia', 'Engineering', 'kg*m2', '''kg*m2|Kilogram square metre|1
kg*cm2|Kilogram square centimetre|.0001
g*cm2|Gram square centimetre|1e-7
lb*ft2|Pound square foot|.0421401100938048
lb*in2|Pound square inch|.0002926396534292
slug*ft2|Slug square foot|1.3558179483314''', 'Rotational inertia; distinct from second moment of area.'),
('stiffness', 'Linear stiffness', 'Engineering', 'N/m', '''N/m|Newton per metre|1
N/mm|Newton per millimetre|1000
kN/m|Kilonewton per metre|1000
lbf/in|Pound force per inch|175.126835246477
lbf/ft|Pound force per foot|14.5939029372064''', ''),
('flow', 'Volume flow', 'Fluids', 'm3/s', '''m3/s|Cubic metre per second|1
m3/h|Cubic metre per hour|.000277777777777778
L/s|Litre per second|.001
L/min|Litre per minute|.0000166666666666667
mL/min|Millilitre per minute|1.66666666666667e-8
gpm-US|US gallon per minute|.0000630901964
gpm-UK|Imperial gallon per minute|.0000757681666666667
cfm|Cubic foot per minute|.0004719474432
cfs|Cubic foot per second|.028316846592''', ''),
('mass-flow', 'Mass flow', 'Fluids', 'kg/s', '''kg/s|Kilogram per second|1
kg/h|Kilogram per hour|.000277777777777778
g/s|Gram per second|.001
g/min|Gram per minute|.0000166666666666667
t/h|Tonne per hour|.277777777777778
lb/s|Pound per second|.45359237
lb/h|Pound per hour|.000125997880555556''', ''),
('dynamic-viscosity', 'Dynamic viscosity', 'Fluids', 'Pa*s', '''Pa*s|Pascal second|1
mPa*s|Millipascal second|.001
P|Poise|.1
cP|Centipoise|.001
lb/(ft*s)|Pound per foot second|1.48816394356955
lbf*s/ft2|Pound force second per square foot|47.8802589803358''', 'Dynamic and kinematic viscosity require density to relate them.'),
('kinematic-viscosity', 'Kinematic viscosity', 'Fluids', 'm2/s', '''m2/s|Square metre per second|1
mm2/s|Square millimetre per second|1e-6
St|Stokes|.0001
cSt|Centistokes|1e-6
ft2/s|Square foot per second|.09290304''', ''),
('surface-tension', 'Surface tension', 'Fluids', 'N/m', '''N/m|Newton per metre|1
mN/m|Millinewton per metre|.001
dyn/cm|Dyne per centimetre|.001
lbf/in|Pound force per inch|175.126835246477''', ''),
('fuel', 'Fuel consumption / economy', 'Everyday', 'm3/m', '''L/100km|Litre per 100 kilometres|1e-8
L/km|Litre per kilometre|1e-6
km/L|Kilometre per litre|-.000001
mpg-US|Mile per US gallon|-.00000235214583333333
mpg-UK|Mile per Imperial gallon|-.00000282480936331822''', 'Economy is reciprocal to consumption. Input must be positive.'),
('conductivity', 'Thermal conductivity', 'Thermal', 'W/(m*K)', '''W/(m*K)|Watt per metre kelvin|1
W/(cm*K)|Watt per centimetre kelvin|100
mW/(m*K)|Milliwatt per metre kelvin|.001
Btu-IT/(h*ft*degF)|BTU IT per hour foot Fahrenheit|1.73073466637139''', ''),
('heat-transfer', 'Heat transfer coefficient', 'Thermal', 'W/(m2*K)', '''W/(m2*K)|Watt per square metre kelvin|1
kW/(m2*K)|Kilowatt per square metre kelvin|1000
Btu-IT/(h*ft2*degF)|BTU IT per hour square foot Fahrenheit|5.67826334111349''', ''),
('heat-capacity', 'Specific heat capacity', 'Thermal', 'J/(kg*K)', '''J/(kg*K)|Joule per kilogram kelvin|1
kJ/(kg*K)|Kilojoule per kilogram kelvin|1000
cal-th/(g*K)|Calorie th per gram kelvin|4184
Btu-IT/(lb*degF)|BTU IT per pound Fahrenheit|4186.8''', ''),
('thermal-resistance', 'Thermal resistance', 'Thermal', 'K/W', '''K/W|Kelvin per watt|1
degC/W|Celsius interval per watt|1
degF*h/Btu-IT|Fahrenheit hour per BTU IT|.526565176728441''', 'Total thermal resistance, not area-normalised insulation R-value.'),
('heat-flux', 'Heat flux', 'Thermal', 'W/m2', '''W/m2|Watt per square metre|1
kW/m2|Kilowatt per square metre|1000
W/cm2|Watt per square centimetre|10000
Btu-IT/(h*ft2)|BTU IT per hour square foot|3.15459074506305''', ''),
('expansion', 'Thermal expansion', 'Thermal', '1/K', '''1/K|Per kelvin|1
um/(m*K)|Micrometre per metre kelvin|1e-6
1/degC|Per Celsius interval|1
1/degF|Per Fahrenheit interval|1.8''', ''),
('charge', 'Electric charge', 'Electrical', 'C', '''C|Coulomb|1
mC|Millicoulomb|.001
uC|Microcoulomb|1e-6
nC|Nanocoulomb|1e-9
Ah|Ampere hour|3600
mAh|Milliampere hour|3.6''', ''),
('current', 'Electric current', 'Electrical', 'A', '''A|Ampere amp|1
mA|Milliampere|.001
uA|Microampere|1e-6
nA|Nanoampere|1e-9
kA|Kiloampere|1000''', ''),
('voltage', 'Voltage', 'Electrical', 'V', '''V|Volt|1
mV|Millivolt|.001
uV|Microvolt|1e-6
kV|Kilovolt|1000
MV|Megavolt|1e6''', ''),
('resistance', 'Electric resistance', 'Electrical', 'ohm', '''ohm|Ohm|1
mohm|Milliohm|.001
uohm|Microohm|1e-6
kohm|Kiloohm|1000
Mohm|Megaohm|1e6
Gohm|Gigaohm|1e9''', 'Symbols are case sensitive: m is milli; M is mega.'),
('conductance', 'Electric conductance', 'Electrical', 'S', '''S|Siemens mho|1
mS|Millisiemens|.001
uS|Microsiemens|1e-6
nS|Nanosiemens|1e-9''', ''),
('capacitance', 'Capacitance', 'Electrical', 'F', '''F|Farad|1
mF|Millifarad|.001
uF|Microfarad|1e-6
nF|Nanofarad|1e-9
pF|Picofarad|1e-12''', ''),
('inductance', 'Inductance', 'Electrical', 'H', '''H|Henry|1
mH|Millihenry|.001
uH|Microhenry|1e-6
nH|Nanohenry|1e-9''', ''),
('magnetic-flux', 'Magnetic flux', 'Magnetism', 'Wb', '''Wb|Weber|1
mWb|Milliweber|.001
uWb|Microweber|1e-6
Mx|Maxwell|1e-8''', ''),
('flux-density', 'Magnetic flux density', 'Magnetism', 'T', '''T|Tesla|1
mT|Millitesla|.001
uT|Microtesla|1e-6
G|Gauss|.0001''', ''),
('illumination', 'Illuminance', 'Light', 'lx', '''lx|Lux|1
klx|Kilolux|1000
fc|Foot candle|10.7639104167097
ph|Phot|10000''', ''),
('activity', 'Radioactivity', 'Radiation', 'Bq', '''Bq|Becquerel|1
kBq|Kilobecquerel|1000
MBq|Megabecquerel|1e6
GBq|Gigabecquerel|1e9
Ci|Curie|3.7e10
mCi|Millicurie|3.7e7
uCi|Microcurie|37000''', ''),
('absorbed-dose', 'Absorbed radiation dose', 'Radiation', 'Gy', '''Gy|Gray|1
mGy|Milligray|.001
uGy|Microgray|1e-6
rad|Rad absorbed dose|.01''', 'Absorbed dose only; conversion to equivalent dose needs radiation weighting.'),
('equivalent-dose', 'Equivalent radiation dose', 'Radiation', 'Sv', '''Sv|Sievert|1
mSv|Millisievert|.001
uSv|Microsievert|1e-6
rem|Rem|.01
mrem|Millirem|.00001''', ''),
('data', 'Data storage', 'Computing', 'bit', '''bit|Bit|1
B|Byte (8 bits)|8
kB|Kilobyte decimal|8000
MB|Megabyte decimal|8e6
GB|Gigabyte decimal|8e9
TB|Terabyte decimal|8e12
KiB|Kibibyte binary|8192
MiB|Mebibyte binary|8388608
GiB|Gibibyte binary|8589934592
TiB|Tebibyte binary|8796093022208''', 'Decimal kB = 1000 B; binary KiB = 1024 B. B is byte; bit is bit.'),
('data-rate', 'Data transfer rate', 'Computing', 'bit/s', '''bit/s|Bit per second bps|1
kbit/s|Kilobit per second kbps|1000
Mbit/s|Megabit per second Mbps|1e6
Gbit/s|Gigabit per second Gbps|1e9
B/s|Byte per second|8
kB/s|Kilobyte per second|8000
MB/s|Megabyte per second|8e6
MiB/s|Mebibyte per second|8388608''', ''),
)


def category(key):
    for record in CATEGORIES:
        if record[0] == key:
            return record
    raise ValueError('Unknown conversion category')


def units(key):
    out = []
    for line in category(key)[4].split('\n'):
        parts = line.split('|')
        out.append((parts[0], parts[1], float(parts[2]), float(parts[3]) if len(parts) > 3 else 0.0))
    return out
