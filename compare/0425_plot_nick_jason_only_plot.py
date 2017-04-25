
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
    '/Users/caojunzhi/Desktop/NYU/Laboratory/task 2016.8.1-12.23/My codes/AnniesLasso_v2/fusion_jason_nick_rms.pkl',
    'rb')
fusion = pickle.load(pkl_file)
pkl_file.close()



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

                'size': 14}

        matplotlib.rc('font', **font)

        f, ax1 = plt.subplots(1, 1)

        alpha = 0.3

        # add mask

        mask = (jason>0)&(jason<1)&(nick>0)&(nick<1)&(teff > 4500) & (teff < 5300)

        jason = jason[mask]
        nick = nick[mask]
        teff = teff[mask]
        logg = logg[mask]
        feh = feh[mask]


        good = np.sum(np.array(jason<nick,dtype=int))/len(jason)
        bad = 1-good

        self.good = good



        # ax1

        ax1.plot(jason,jason, "k", alpha=0.3, linewidth=2)

        ax1.set_title("$Our\quad method \quad works \quad better \quad for \quad %.2f\quad percent\quad stars$" % (
                     good * 100))

        ax1.set_xlabel('$RMS\quad of\quad RVs\quad from \quad our\quad method \quad (km/s)$', fontsize=20,
                       weight="bold")
        ax1.set_ylabel('$RMS\quad of\quad RVs\quad from \quad Nick\'s \quad method \quad (km/s)$', fontsize=20,
                       weight="bold")

        ax1.legend(bbox_to_anchor=(0, 1), loc=2, borderaxespad=0.)
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

        mask = (jason > 0) & (jason < 1) & (nick > 0) & (nick < 1)&((logg > 2) & (logg < 3.25))

        jason = jason[mask]
        nick = nick[mask]
        teff = teff[mask]
        logg = logg[mask]
        feh = feh[mask]




        font = {'family': 'normal',

                'size': 14}

        matplotlib.rc('font', **font)

        f, ax1 = plt.subplots(1, 1)

        alpha = 0.3

        good = self.good



        # ax1

        ax1.plot(jason,jason, "k", alpha=0.3, linewidth=2)

        ax1.set_title("$Our\quad method \quad works \quad better \quad for \quad %.2f\quad percent\quad stars$" % (
                     good * 100))

        ax1.set_xlabel('$RMS\quad of\quad RVs\quad from \quad our\quad method \quad (km/s)$', fontsize=20,
                       weight="bold")
        ax1.set_ylabel('$RMS\quad of\quad RVs\quad from \quad Nick\'s \quad method \quad (km/s)$', fontsize=20,
                       weight="bold")

        ax1.legend(bbox_to_anchor=(0, 1), loc=2, borderaxespad=0.)
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

                'size': 14}

        matplotlib.rc('font', **font)

        f, ax1 = plt.subplots(1, 1)

        alpha = 0.3

        print(feh.shape)
        print(jason.shape)
        print(nick.shape)

        good = self.good



        # ax1

        ax1.plot(jason,jason, "k", alpha=0.3, linewidth=2)

        ax1.set_title("$Our\quad method \quad works \quad better \quad for \quad %.2f\quad percent\quad stars$" % (
                     good * 100))

        ax1.set_xlabel('$RMS\quad of\quad RVs\quad from \quad our\quad method \quad (km/s)$', fontsize=20,
                       weight="bold")
        ax1.set_ylabel('$RMS\quad of\quad RVs\quad from \quad Nick\'s \quad method \quad (km/s)$', fontsize=20,
                       weight="bold")

        ax1.legend(bbox_to_anchor=(0, 1), loc=2, borderaxespad=0.)
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


    def plot_teff_logg(self):

        teff = self.teff
        logg = self.logg
        feh = self.feh

        font = {'family': 'normal',
                'size': 14}

        matplotlib.rc('font', **font)

        f, ax1 = plt.subplots(1, 1)

        alpha = 0.3
        # ax1

        ax1.set_ylabel("$Teff \quad (K)$", fontsize=20)
        ax1.set_xlabel("$logg \quad (dex)$", fontsize=20)

        f.subplots_adjust(right=0.8)

        pl = ax1.scatter(logg, teff, marker='o', c=feh,
                         vmin=np.min(feh), vmax=np.max(feh), alpha=alpha, cmap="RdBu")

        cbar_ax = f.add_axes([0.85, 0.15, 0.02, 0.7])

        cb = f.colorbar(pl, cax=cbar_ax)

        cb.solids.set_edgecolor("face")

        cb.set_label("$FeH \quad (dex)$", fontsize=20)

        matplotlib.rcParams['text.usetex'] = True
        matplotlib.rcParams['text.latex.unicode'] = True

        f.suptitle(r'\textbf{Teff vs Logg for some stars in DR13}', fontsize=30, weight="bold")

        # save them:

        fig = matplotlib.pyplot.gcf()

        # adjust the size based on the number of visit

        fig.set_size_inches(14.5, 8.5)

        save_path = "/Users/caojunzhi/Downloads/upload_20170425/" + "Teff_logg" + ".png"
        fig.savefig(save_path, dpi=500)

        plt.close()




model = plot()

print(fusion.shape)
model.read_data(old=fusion[:,2],jason=fusion[:,0],nick= fusion[:,1],teff=fusion[:,3],logg=fusion[:,4],feh=fusion[:,5])



model.plot_RV_rms_before_after_teff()
model.plot_RV_rms_before_after_logg()
model.plot_RV_rms_before_after_feh()

model.plot_teff_logg()



