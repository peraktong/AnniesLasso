
from scipy import stats
import numpy as np

import matplotlib.pyplot as plt
import matplotlib
import pickle
import scipy

from astropy.io import fits
from astropy.table import Table
from astropy.coordinates import SkyCoord
from astropy.time import Time

# read data:



pkl_file = open(
    '/Users/caojunzhi/Desktop/NYU/Laboratory/task 2016.8.1-12.23/My codes/AnniesLasso_v2/dr13_nick_fits.pkl',
    'rb')
nick_path = pickle.load(pkl_file)
pkl_file.close()

pkl_file = open(
    '/Users/caojunzhi/Desktop/NYU/Laboratory/task 2016.8.1-12.23/My codes/AnniesLasso_v2/dr13_mine_fits.pkl',
    'rb')
jason_path = pickle.load(pkl_file)
pkl_file.close()


def MJD2BJD(mjd, target_coord, site_location=(-105.820417,32.780361)):
    """do the conversion
mjd -- input mjd, scale is utc
target_coord -- the coordinate of the target, in astropy.coord format,
to caculate the light travel time
site_location -- location of the telescope, to make accurate calcualtion of
light travel time and tdb conversion. Not very important here. The default value
is for Greenwich Observatory.
"""
    t = Time(mjd, format='mjd', scale='utc', location=site_location)
    # calculate light travel time
    ltt = t.light_travel_time(target_coord)
    # print(t, ltt)
    # convert t to tdb, and add light travel time
    t_out = (t.tdb + ltt).jd

    return t_out

"""
c = SkyCoord(RA,DEC, frame='icrs', unit='deg')

BJD = MJD2BJD(MJD,c)

"""


# plot:

class plot():

    def read_data(self,old,jason,nick,teff,logg,feh):

        self.old = old
        self.jason = jason
        self.nick = nick

        self.teff = teff
        self.logg = logg
        self.feh = feh

    def plot_RV_rms_before_after_teff(self):

        jason = self.jason
        nick = self.nick

        teff = self.teff
        logg = self.logg
        feh = self.feh




        font = {'family': 'normal',
                'weight': 'bold',
                'size': 14}

        matplotlib.rc('font', **font)

        f, ax1 = plt.subplots(1, 1)

        alpha = 0.3

        # add mask

        mask = (jason>0)&(jason<1)&(nick>0)&(nick<1)

        jason = jason[mask]
        nick = nick[mask]
        teff = teff[mask]
        logg = logg[mask]
        feh = feh[mask]


        good = np.sum(np.array(jason<nick,dtype=int))/len(jason)
        bad = 1-good



        # ax1

        ax1.plot(jason,jason, "k", alpha=0.3, linewidth=2)

        ax1.plot([], [], "ro",
                 label="Our\quadmethod\quadworks\quadbetter\quadfor\ %.2f\quadstars" % (
                 good * 100))

        ax1.set_xlabel('$RMS\quad of\quad RVs\quad from \quad our\quad method \quad (km/s)$', fontsize=20,
                       weight="bold")
        ax1.set_ylabel('$RMS\quad of\quad RVs\quad from \quad Nick\'s \quad method \quad (km/s)$', fontsize=20,
                       weight="bold")

        ax1.legend()
        f.subplots_adjust(right=0.8)

        pl = ax1.scatter(jason,nick, marker='o', c=teff,
                         vmin=np.min(teff), vmax=np.max(teff), alpha=alpha, cmap=plt.cm.viridis)

        cbar_ax = f.add_axes([0.85, 0.15, 0.02, 0.7])
        cb = f.colorbar(pl, cax=cbar_ax)

        cb.solids.set_edgecolor("face")

        cb.set_label("$Teff \quad (K)$", fontsize=20, weight="bold")

        matplotlib.rcParams['text.usetex'] = True
        matplotlib.rcParams['text.latex.unicode'] = True

        f.suptitle(r'\textbf{Comparison of RMS for some stars in DR13}', fontsize=25)

        # save them:

        fig = matplotlib.pyplot.gcf()

        # adjust the size based on the number of visit

        fig.set_size_inches(14.5, 11.5)

        save_path = "/Users/caojunzhi/Downloads/upload_20170425/" + "RV_rms_nick_jason_teff" + ".png"
        fig.savefig(save_path, dpi=500)

        plt.close()

    def plot_RV_rms_before_after_logg(self):

        jason = self.jason
        nick = self.nick

        teff = self.teff
        logg = self.logg
        feh = self.feh

        mask = (jason > 0) & (jason < 1) & (nick > 0) & (nick < 1)

        jason = jason[mask]
        nick = nick[mask]
        teff = teff[mask]
        logg = logg[mask]
        feh = feh[mask]




        font = {'family': 'normal',
                'weight': 'bold',
                'size': 14}

        matplotlib.rc('font', **font)

        f, ax1 = plt.subplots(1, 1)

        alpha = 0.3

        good = np.sum(np.array(jason<nick,dtype=int))/len(jason)
        bad = 1-good



        # ax1

        ax1.plot(jason,jason, "k", alpha=0.3, linewidth=2)

        ax1.plot([], [], "ro",
                 label="Our\quadmethod\quadworks\quadbetter\quadfor\ %.2f\quadstars" % (
                     good * 100))

        ax1.set_xlabel('$RMS\quad of\quad RVs\quad from \quad our\quad method \quad (km/s)$', fontsize=20,
                       weight="bold")
        ax1.set_ylabel('$RMS\quad of\quad RVs\quad from \quad Nick\'s \quad method \quad (km/s)$', fontsize=20,
                       weight="bold")

        ax1.legend()
        f.subplots_adjust(right=0.8)

        pl = ax1.scatter(jason,nick, marker='o', c=logg,
                         vmin=np.min(logg), vmax=np.max(logg), alpha=alpha, cmap=plt.cm.viridis)

        cbar_ax = f.add_axes([0.85, 0.15, 0.02, 0.7])
        cb = f.colorbar(pl, cax=cbar_ax)

        cb.solids.set_edgecolor("face")

        cb.set_label("$Logg \quad (dex)$", fontsize=20, weight="bold")

        matplotlib.rcParams['text.usetex'] = True
        matplotlib.rcParams['text.latex.unicode'] = True

        f.suptitle(r'\textbf{Comparison of RMS for some stars in DR13}', fontsize=25)

        # save them:

        fig = matplotlib.pyplot.gcf()

        # adjust the size based on the number of visit

        fig.set_size_inches(14.5, 11.5)

        save_path = "/Users/caojunzhi/Downloads/upload_20170425/" + "RV_rms_nick_jason_logg" + ".png"
        fig.savefig(save_path, dpi=500)

        plt.close()

    def plot_RV_rms_before_after_feh(self):


        jason = self.jason
        nick = self.nick

        teff = self.teff
        logg = self.logg
        feh = self.feh

        mask = (jason > 0) & (jason < 1) & (nick > 0) & (nick < 1)

        jason = jason[mask]
        nick = nick[mask]
        teff = teff[mask]
        logg = logg[mask]
        feh = feh[mask]




        font = {'family': 'normal',
                'weight': 'bold',
                'size': 14}

        matplotlib.rc('font', **font)

        f, ax1 = plt.subplots(1, 1)

        alpha = 0.3

        print(feh.shape)
        print(jason.shape)
        print(nick.shape)

        good = np.sum(np.array(jason<nick,dtype=int))/len(jason)
        bad = 1-good



        # ax1

        ax1.plot(jason,jason, "k", alpha=0.3, linewidth=2)

        ax1.plot([], [], "ro",
                 label="Our\quadmethod\quadworks\quadbetter\quadfor\ %.2f\quadstars" % (
                     good * 100))

        ax1.set_xlabel('$RMS\quad of\quad RVs\quad from \quad our\quad method \quad (km/s)$', fontsize=20,
                       weight="bold")
        ax1.set_ylabel('$RMS\quad of\quad RVs\quad from \quad Nick\'s \quad method \quad (km/s)$', fontsize=20,
                       weight="bold")

        ax1.legend()
        f.subplots_adjust(right=0.8)

        pl = ax1.scatter(jason,nick, marker='o', c=feh,
                         vmin=np.min(feh), vmax=np.max(feh), alpha=alpha, cmap=plt.cm.viridis)

        cbar_ax = f.add_axes([0.85, 0.15, 0.02, 0.7])
        cb = f.colorbar(pl, cax=cbar_ax)

        cb.solids.set_edgecolor("face")

        cb.set_label("$FeH \quad (dex)$", fontsize=20, weight="bold")

        matplotlib.rcParams['text.usetex'] = True
        matplotlib.rcParams['text.latex.unicode'] = True

        f.suptitle(r'\textbf{Comparison of RMS for some stars in DR13}', fontsize=25)

        # save them:

        fig = matplotlib.pyplot.gcf()

        # adjust the size based on the number of visit

        fig.set_size_inches(14.5, 11.5)

        save_path = "/Users/caojunzhi/Downloads/upload_20170425/" + "RV_rms_nick_jason_feh" + ".png"
        fig.savefig(save_path, dpi=500)

        plt.close()



class read_data():


    def Read_rms(self,jason, nick):
        font = {'family': 'normal',

                'size': 24}

        matplotlib.rc('font', **font)

        table = Table.read(nick,hdu=1)
        image = fits.open(jason)

        VHELIO = image[11].data

        shift = image[1].data[2:] / 1000

        print(image[13].data.shape)
        print(shift.shape)
        print(VHELIO.shape)

        # BJD
        BJD = image[13].data

        # BJD for Nick

        teff = image[8].data[0,0]
        logg = image[8].data[0,1]
        feh = image[8].data[0,2]


        MJD = table["MJD"]
        RA = table["RA"][0]
        DEC = table["DEC"][0]
        c = SkyCoord(RA, DEC, frame='icrs', unit='deg')

        ni = len(MJD)
        BJD_nick = []
        for j in range(0, ni):
            BJD_nick.append(MJD2BJD(MJD[j], c))

        VHELIO_nick = table["VHELIO"]

        rms_old = np.std(VHELIO)
        rms_nick = np.std(VHELIO_nick)
        rms_jason = np.std(VHELIO + shift)

        self.VHELIO = VHELIO
        self.VHELIO_nick = VHELIO_nick
        self.shift = shift
        self.teff = teff
        self.logg = logg
        self.feh = feh

        return rms_old, rms_nick, rms_jason


##plot

# construct a array : rms_jason, rms_nick,teff,logg,feh

jason = []
nick = []
old = []

teff = []
logg = []
feh = []

model = read_data()

for i in range(0,len(jason_path)):

    
    print("doing %d"%i)

    try:
        print(jason_path[i])
        print(nick_path[i])

        old_i, nick_i, jason_i = model.Read_rms(jason=jason_path[i], nick=nick_path[i])

        jason.append(jason_i)
        nick.append(nick_i)
        old.append(old_i)

        teff.append(model.teff)
        logg.append(model.logg)
        feh.append(model.feh)
    except IndexError:
        print("This one failed")

    except OSError:
        print("This one failed")


old =np.array(old)
jason = np.array(jason)
nick = np.array(nick)

teff = np.array(teff)
logg = np.array(logg)
feh = np.array(feh)


fusion = np.c_[jason,nick,old,teff,logg,feh]
fusion = np.array(fusion)

# save it:


output = open('fusion_jason_nick_rms.pkl', 'wb')
pickle.dump(fusion, output)
output.close()









