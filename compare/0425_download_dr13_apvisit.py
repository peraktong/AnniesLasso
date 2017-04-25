
from astropy.table import Table
import numpy as np
import urllib.request



# read data
apvisit = Table.read("/Users/caojunzhi/Desktop/NYU/Laboratory/task 2016.8.1-12.23/My codes/AnniesLasso_v2/allStar-l30e.2.fits",hdu=1)
#image=fits.open("allStar-v603.fits")





N = len(apvisit)
print(N)

print(apvisit[2])



for i,row in enumerate(apvisit):


    length = len(row["ALL_VISITS"].split(","))
    visit = row["ALL_VISITS"].split(",")

    for j in range(0,length):

        b = visit[j]
        b = b + ".fits"
        b = "apVisit-" + b




        try:

            # path = "curl -o " + b + " http://data.sdss3.org/sas/dr13/apogee/spectro/redux/r6/stars/apo25m/"+str(row["LOCATION_ID"])+"/" + b
            path = "https://data.sdss.org/sas/dr13/apogee/spectro/redux/r6/apo25m/" + str(
                np.array(b.split("-"))[2]) + "/" + str(np.array(b.split("-"))[3]) + "/" + b
            save = "/Volumes/Data_2TB/Data/APOGEE_DR13_Apvisit/"
            loc = save + b

            urllib.request.urlretrieve(path, loc)

            print(path)
            print("doing star %i" % i)

        except urllib.error.HTTPError:
            print("%s not found" % b)
            print(path)

        except IndexError:
            print("%s not found" % b)












