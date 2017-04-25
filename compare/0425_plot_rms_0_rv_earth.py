from PyAstronomy import pyasl
import numpy as np
import matplotlib.pyplot as plt


jd = 2.476468576e6
# Coordinates of Sirius
ra  = 101.28715535
dec = -16.71611587

# in Km/s
heli = []
bary = []

date = [1,100,150,165,225,297]

for i in date:

    heli_i, bary_i = pyasl.baryCorr(jd+i, ra, dec, deq=2000.0)

    heli.append(heli_i)
    bary.append(bary_i)

bary = np.array(bary)
print(np.std(bary))
print(bary.shape)
plt.plot(bary,"ro")
plt.show()
