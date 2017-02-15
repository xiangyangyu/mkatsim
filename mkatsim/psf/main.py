"""Simulate PSF, Image and Dirty Image"""

from __future__ import print_function
from datetime import datetime, timedelta

import glob
import matplotlib.pyplot as plt
import numpy
import os
import shutil
import subprocess
import tempfile

import astropy
from astropy import units as u
from astropy.coordinates import Longitude, Latitude, EarthLocation

import casacore.tables

from makems import ms_make
import coordinates
import plot

def main(opts, args):
    # TODO:
    #   possibly be more explicit about what opts & args are accepted -- would
    #   be helpful info for when one wants to call main() from somewhere else
    # Reference location
    lon = Longitude(opts.lon.strip(), u.degree, wrap_angle=180*u.degree, copy=False)
    lat = Latitude(opts.lat.strip(), u.degree, copy=False)
    height = u.Quantity(float(opts.alt.strip()), u.m, copy=False)
    ref_location = EarthLocation(lat=lat.to(u.deg).value, lon=lon.to(u.deg).value, height=height.to(u.m).value)
    # Array location
    if len(args) > 0:
        if opts.enu:
            [array_geocentric, ant_list] = coordinates.enu_read(args[0], ref_location)
        else:
            raise RuntimeError('Coordinate system not implemented yet')

## Create CASA ANTENNA table for antenna positions
    if opts.tblname is None:
        opts.tblname = '%s_ANTENNA'%opts.array
        import anttbl
        try: anttbl.make_tbl(opts.tblname, ant_list)
        except: raise

## Make dummy measurement set for simulations
    msname=None
    nscans=int(12./opts.dtime) # number scans
    ## XXX: UNUSED
    dintegration=opts.synthesis*3600/nscans # integration time per scan
    declinations_deg = opts.declination.strip().split(',')
    for opts.declination in declinations_deg:
        if opts.stime is not None:
            starttime_object = datetime.strptime(opts.stime, "%Y/%m/%d/%H:%M")
        else:
            starttime_object = datetime.now()

        mslist = []
        for scan in range(nscans):
            starttime = starttime_object + timedelta(seconds=scan*opts.dtime*3600.)
            opts.stime=starttime.strftime("%Y/%m/%d/%H:%M")
            mslist.append(ms_make(opts))

        if len(mslist) > 1:
            msname='%s_%sdeg_%.2fhr.ms_p0' % (opts.array, opts.declination, opts.synthesis)
            casacore.tables.msconcat(mslist,msname,concatTime=True)
        else: msname = mslist[0]

##Clean simulated data to get psf
        try:
            subprocess.check_call([
                'wsclean',
                '-j', '4',
                '-size', '7200', '7200',
                '-scale', '0.5asec',
                '-weight', 'briggs', str(opts.robust),
                # '-weight', ' '.join((opts.weight, str(opts.robust))),
                '-make-psf',
                '-fitbeam',
                '-name', msname,
                msname,
                ])
        except subprocess.CalledProcessError as e:
            # TODO: handle or report exception here, maybe
            pass

    sliceout=None
    uvout=None
## Convert wsclean generated fits files to PNG
    from fits2png import fits2png
    for fitsfile in glob.glob('*psf.fits'):
        if opts.savegraph:
            fits2png(fitsfile,area=0.04,contrast=0.05,cmap='jet')

            sliceout = '%s-slice.png'%os.path.splitext(os.path.basename(fitsfile))[0]
            uvout = '%s-uv.png'%os.path.splitext(os.path.basename(msname))[0]
## Slice through the major axis of the PSF
        plot.slicepsf(fitsfile, output=sliceout)
## UV coverage of measurement set
        plot.uv(msname, output=uvout)

    if opts.verbose:
        try: plt.show()
        except: pass # nothing to show

# -fin-
