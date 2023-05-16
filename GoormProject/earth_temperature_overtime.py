
#%%
from urllib.request import urlretrieve
URL = 'http://go.gwu.edu/engcomp1data5?accessType=DOWNLOAD'
urlretrieve(URL, 'land_global_temperature_anomaly-1880-2016.csv')

import numpy
fname = '/home/y981010/vscode/machine_learning/land_global_temperature_anomaly-1880-2016.csv'
year, temp_anomaly = numpy.loadtxt(fname, delimiter=',', skiprows=5, unpack=True)

from matplotlib import pyplot
#%%
pyplot.plot(year, temp_anomaly);

pyplot.rc('font', family='serif', size='18')
pyplot.figure(figsize=(10,5))
#%%
pyplot.plot(year,temp_anomaly, color='#2929a3', linestyle='-', linewidth=1)
pyplot.title('Land global temperature anomalies. \n')
pyplot.xlabel('Year')
pyplot.ylabel('Land temperature anomaly [°C]')
pyplot.grid();

w = numpy.sum(temp_anomaly*(year - year.mean())) / numpy.sum(year*(year-year.mean()))
b = a_0 = temp_anomaly.mean() - w * year.mean()
reg = b + w*year
#%%
pyplot.figure(figsize=(10,5))
pyplot.plot(year, temp_anomaly, color='#2929a3', linestyle='-', linewidth=1, alpha=0.5)
pyplot.plot(year, reg, 'k--', linewidth=2, label='Linear regression')
pyplot.xlabel('Year')
pyplot.ylabel('Land temperature anomally [º C]')
pyplot.legend(loc='best', fontsize=15)
pyplot.grid();
# %%
