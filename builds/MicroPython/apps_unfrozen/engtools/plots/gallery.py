"""Small synthetic examples for inspecting shared plot layouts and controls."""

CHOICES = (
    ('2D equations', 'Colored curves and legend'),
    ('2D shaded region', 'Implicit circle and inequality'),
    ('2D sampled data', 'Line, points, labels and units'),
    ('3D function', 'Saddle surface and camera controls'),
    ('3D implicit surface', 'Sphere with equal XYZ units'),
)


def specification(index):
    if index == 0:
        return '2d', {'title':'Waves','bounds':[-10,10,-1.5,1.5], 'legend':True,
                      'axes':{'x':{'label':'x'},'y':{'label':'Amplitude'}},
                      'series':[{'expression':'sin(x)','name':'sin(x)'},
                                {'expression':'cos(x)','name':'cos(x)'}]}
    if index == 1:
        return '2d', {'title':'Shaded disk','bounds':[-4.5,4.5,-4.5,4.5], 'equal_scale':True,
                      'series':[{'expression':'x^2+y^2<=9'}, {'expression':'x^2+y^2=9'}]}
    if index == 2:
        import math
        points=[(i*6/120, math.exp(-.65*i*6/120)*math.cos(3*i*6/120)) for i in range(121)]
        samples=[(x,y+.03*math.sin(9*x)) for x,y in points[::8]]
        return '2d', {'title':'Sampled data','bounds':[0,6,-1.3,1.3],'legend':True,
                      'axes':{'x':{'label':'Time','unit':'s'},'y':{'label':'Response','unit':'V'}},
                      'series':[{'type':'samples','name':'Reference','points':points,'style':'line'},
                                {'type':'samples','name':'Samples','points':samples,'style':'scatter'}]}
    if index == 3:
        return '3d', {'title':'Saddle','range':3,'resolution':12,
                      'surfaces':[{'expression':'z=0.12*(x^2-y^2)'}]}
    if index == 4:
        return '3d', {'title':'Sphere','range':2,'resolution':12,
                      'surfaces':[{'expression':'x^2+y^2+z^2=1'}]}
    raise ValueError('Unknown plotting example')
