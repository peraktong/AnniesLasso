#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
A pedestrian version of The Cannon.
"""

from __future__ import (division, print_function, absolute_import,
                        unicode_literals)

__all__ = ["CannonModel"]

import logging
from numpy.linalg import inv
import numpy as np
import scipy.optimize as op
import os
from scipy.ndimage import gaussian_filter
# try to use gnumpy
#import gnumpy as gpu

from . import (model, utils)


logger = logging.getLogger(__name__)


class CannonModel(model.BaseCannonModel):
    """
    A generalised Cannon model for the estimation of arbitrary stellar labels.

    :param labelled_set:
        A set of labelled objects. The most common input form is a table with
        columns as labels, and stars/objects as rows.

    :type labelled_set:
        :class:`~astropy.table.Table` or a numpy structured array

    :param normalized_flux:
        An array of normalized fluxes for stars in the labelled set, given as
        shape `(num_stars, num_pixels)`. The `num_stars` should match the number
        of rows in `labelled_set`.

    :type normalized_flux:
        :class:`np.ndarray`

    :param normalized_ivar:
        An array of inverse variances on the normalized fluxes for stars in the
        labelled set. The shape of the `normalized_ivar` array should match that
        of `normalized_flux`.

    :type normalized_ivar:
        :class:`np.ndarray`

    :param dispersion: [optional]
        The dispersion values corresponding to the given pixels. If provided, 
        this should have length `num_pixels`.

    :type dispersion:
        :class:`np.array`

    :param threads: [optional]
        Specify the number of parallel threads to use. If `threads > 1`, the
        training and prediction phases will be automagically parallelised.

    :type threads:
        int

    :param pool: [optional]
        Specify an optional multiprocessing pool to map jobs onto.
        This argument is only used if specified and if `threads > 1`.
    
    :type pool:
        bool
    """
    def __init__(self, *args, **kwargs):
        super(CannonModel, self).__init__(*args, **kwargs)


    @model.requires_model_description
    def train(self, fixed_scatter=True, **kwargs):
        """
        Train the model based on the labelled set.
        """
        
        # Experimental/asthetic keywords:
        # use_neighbouring_pixels, progressbar
        assert fixed_scatter, "Are you refactoring?"
        if self.s2 is None:
            logger.warn("Fixing and assuming s2 = 0")
            self.s2 = 0

        if fixed_scatter and self.s2 is None:
            raise ValueError("intrinsic pixel variance (s2) must be set "
                             "before training if fixed_scatter is set to True")

        # We default use_neighbouring_pixels to None so that we can default it
        # to True later if we want, but we can warn the user if they explicitly
        # set it to True and we intend to ignore it.
        use_neighbouring_pixels = kwargs.pop("use_neighbouring_pixels", None)
        if self.theta is None:
            if use_neighbouring_pixels is None:
                use_neighbouring_pixels = True
            initial_theta = [None] * self.dispersion.size

        else:
            # Since theta is already set, we will ignore neighbouring pixels.
            if use_neighbouring_pixels is True:
                use_neighbouring_pixels = False
                logger.warn("Ignoring neighbouring pixels because theta is "
                            "already provided.")
            initial_theta = self.theta.copy()
    
        # Initialize the scatter.
        initial_s2 = self.s2 if fixed_scatter \
            else 0.01**2 * np.ones_like(self.dispersion)

        # Prepare the method and arguments.
        fitting_function = kwargs.pop("function", _fit_pixel)
        kwds = {
            "fixed_scatter": fixed_scatter,
            "design_matrix": self.design_matrix,
            "op_kwargs": kwargs.pop("op_kwargs", {}),
            "op_bfgs_kwargs": kwargs.pop("op_bfgs_kwargs", {})
        }

        N_stars, N_pixels = self.normalized_flux.shape
        logger.info("Training {0}-label {1} with {2} stars and {3} pixels/star"\
            .format(len(self.vectorizer.label_names), type(self).__name__,
                N_stars, N_pixels))

        # Arguments:
        # initial_theta, initial_s2, flux, ivar, design_matrix_mask, 
        # [additional_args], 
        # design_matrix, **kwargs
        args = [initial_theta, initial_s2, self.normalized_flux.T, 
            self.normalized_ivar.T, self.censored_vectorizer_terms]
        args.extend(kwargs.get("additional_args", []))

        # Write the design matrix to a temporary file.
        temporary_filenames = []
        """
        Not clear whether this is still needed because this issue was
        complicated by some Legacy Python issues. But I'm not ready to remove
        this comment because I have forgotten about this issue twice before in
        the past and it ruined my day.

        temporary_filename = utils._pack_value(self.design_matrix)
        kwds["design_matrix"] = temporary_filename
        temporary_filenames.append(temporary_filename)
        """

        N_items = N_pixels if kwargs.get("progressbar", True) else 0

        # Wrap the function so we can parallelize it out.
        mapper = map if self.pool is None else self.pool.map
        try:
            f = utils.wrapper(fitting_function, None, kwds, N_items)
            if self.pool is None and use_neighbouring_pixels:
                output = []
                last_theta = []
                for j, row in enumerate(zip(*args)):
                    if j > 0:
                        # Update with determined theta from neighbour pixel.
                        row = list(row)
                        row[0] = last_theta
                        row = tuple(row)
                    output.append(f(row))
                    last_theta = output[-1][0][:self.design_matrix.shape[1]]
            else:
                output = mapper(f, [row for row in zip(*args)])

        except KeyboardInterrupt:
            logger.warn("Keyboard interrupted training step!")

            # Clean up any temporary files in case we are debugging.
            for filename in temporary_filenames:
                if os.path.exists(filename): os.remove(filename)

            # re-raise a suppressed exception?
            raise


        # Clean up any temporary files.
        for filename in temporary_filenames:
            if os.path.exists(filename): os.remove(filename)

        # Unpack the results.
        results, metadata = zip(*output)
        results = np.array(results)

        self.theta, self.s2 = (results[:, :-1], results[:, -1])

        return None


    @model.requires_training_wheels
    def predict(self, labels, **kwargs):
        """
        Predict spectra from the trained model, given the labels.

        :param labels:
            The label values to predict model spectra of. The length and order
            should match what is required of the vectorizer
            (`CannonModel.vectorizer.label_names`).
        """
        return np.dot(self.theta, self.vectorizer(labels).T).T


    @model.requires_training_wheels

    # By Jason Cao


    def fitting_spectrum_parameters(self,normalized_flux,normalized_ivar,inf_flux):
        nor = normalized_flux
        inf = inf_flux
        ivar = normalized_ivar
        n_pixel = nor[0, :].size
        n_star = inf[:, 0].size
        one = np.ones(n_star)

        # new method for building matrix
        x_data = np.c_[one,inf]
        x_data = x_data[:,0:n_pixel]

        y_data =inf

        z_data = np.c_[inf,one]
        z_data = z_data[:,1:n_pixel+1]

        # fit
        # It's not good. let's do it one star each time.

        left = np.zeros((3,3))
        right = np.zeros(3)

        for p in range(0, n_star):

            x_data_p = x_data[p, :]
            y_data_p = y_data[p, :]
            z_data_p = z_data[p, :]
            nor_p = nor[p, :]
            ivar_p = ivar[p, :]

            # construct
            ivar_r = ivar_p.ravel()
            ni = len(ivar_r)
            print("calculating parameters",p,"{:.2f}%".format(p/n_star*100))
            c = np.zeros((ni, ni))

            for i in range(0, ni):
                c[i, i] = ivar_r[i]

            y = nor_p.ravel()
            a = np.c_[np.c_[x_data_p.ravel(), y_data_p.ravel()], z_data_p.ravel()]

            left += np.dot(np.dot(a.T, c), a)
            right += np.dot(np.dot(a.T,c), y)

        parameters = np.dot(inv(left), right)
        opt_flux = parameters[0]*x_data+parameters[1]*y_data+parameters[2]*z_data
        print("finish fitting")

        # build theta:
        zero = np.ones(n_pixel)

        theta_x = np.c_[zero,self.theta]
        theta_x = x_data[:,0:n_pixel]

        theta_y =inf

        theta_z = np.c_[self.theta,zero]
        theta_z = z_data[:,1:n_pixel+1]

        theta_opt = parameters[0]*theta_x+parameters[1]*theta_y+parameters[2]*theta_z

        return opt_flux,theta_opt,parameters


    # return the parameters of each star.
    # Now the uncertainty of parameters is also calculated
    # The structure of the uncertainty is each row is aa,ab,ac ba....
    # so the dimension is 3*3*N, which is a 3 dimension array
    # use self.uncertainty to store
    # Now the model

    def fitting_spectrum_parameters_single(self,normalized_flux,normalized_ivar,inf_flux):
        nor = normalized_flux
        inf = inf_flux
        ivar = normalized_ivar
        n_pixel = nor[0, :].size
        n_star = inf[:, 0].size
        one = np.ones(n_star)

        # new method for building matrix
        x_data = np.c_[one,inf]
        x_data = x_data[:,0:n_pixel]

        y_data =inf

        z_data = np.c_[inf,one]
        z_data = z_data[:,1:n_pixel+1]

        self.x_data =x_data
        self.y_data =y_data
        self.z_data =z_data

        # fit
        # It's not good. let's do it one star each time.

        left = np.zeros((3,3))
        right = np.zeros(3)
        un = np.zeros((3,3))
        parameters=np.array([0,1,0])
        opt_flux = np.ones(n_pixel)

        for p in range(0, n_star):

            x_data_p = x_data[p, :]
            y_data_p = y_data[p, :]
            z_data_p = z_data[p, :]
            nor_p = nor[p, :]
            ivar_p = ivar[p, :]

            # construct
            ivar_r = ivar_p.ravel()
            ni = len(ivar_r)
            print("calculating parameters",p,"{:.2f}%".format(p/n_star*100))
            c = np.zeros((ni, ni))

            for i in range(0, ni):
                c[i, i] = ivar_r[i]

            y = nor_p.ravel()
            a = np.c_[np.c_[x_data_p.ravel(), y_data_p.ravel()], z_data_p.ravel()]

            left = np.dot(np.dot(a.T, c), a)
            right = np.dot(np.dot(a.T,c), y)

            un_p = inv(left)

            parameters_p =np.dot(inv(left), right)

            opt_flux = np.vstack((opt_flux,parameters_p[0]*x_data_p+parameters_p[1]*y_data_p+parameters_p[2]*z_data_p))
            parameters = np.vstack((parameters,parameters_p))
            print(parameters_p)
            un = np.dstack((un,un_p))
        print("finish fitting")
        # reshape
        parameters = parameters[1:(n_star+1),:]
        opt_flux = opt_flux[1:(n_star + 1), :]
        un = un[:,:,1:(n_star + 1)]
        self.uncertainty = un
        self.opt_flux = opt_flux

        # the shape of the uncertainty is 3*3*N

        print(parameters.shape,n_star,opt_flux.shape,un.shape)

        return opt_flux,parameters


    def fitting_spectrum_parameters_single_5(self,normalized_flux,normalized_ivar,inf_flux):
        nor = normalized_flux
        inf = inf_flux
        ivar = normalized_ivar
        n_pixel = nor[0, :].size
        n_star = inf[:, 0].size
        one = np.ones(n_star)

        # new method for building matrix
        l_1 = np.c_[one,inf]
        l_1 = l_1[:,0:n_pixel]

        l_2 = np.c_[one,l_1]
        l_2 = l_2[:, 0:n_pixel]


        m_0 =inf

        r_1 = np.c_[inf,one]
        r_1 = r_1[:,1:n_pixel+1]

        r_2 = np.c_[r_1,one]
        r_2 = r_2[:, 1:n_pixel + 1]

        # fit
        # It's not good. let's do it one star each time.

        un = np.zeros((5,5))
        parameters=np.array([0,0,0,0,0])
        opt_flux = np.ones(n_pixel)

        for p in range(0, n_star):

            l_2_p =l_2[p,:]
            l_1_p = l_1[p, :]
            m_0_p = m_0[p, :]
            r_1_p = r_1[p, :]
            r_2_p = r_2[p, :]


            nor_p = nor[p, :]
            ivar_p = ivar[p, :]

            # construct
            ivar_r = ivar_p.ravel()
            ni = len(ivar_r)
            print("calculating parameters_5",p,"{:.2f}%".format(p/n_star*100))
            c = np.zeros((ni, ni))

            for i in range(0, ni):
                c[i, i] = ivar_r[i]

            y = nor_p.ravel()

            a = np.c_[np.c_[l_2_p.ravel(), l_1_p.ravel()], m_0_p.ravel()]
            a = np.c_[a,r_1_p.ravel()]
            a = np.c_[a,r_2_p.ravel()]




            left = np.dot(np.dot(a.T, c), a)
            right = np.dot(np.dot(a.T,c), y)

            un_p = inv(left)

            parameters_p =np.dot(inv(left), right)

            opt_flux = np.vstack((opt_flux,parameters_p[0]*l_2_p+parameters_p[1]*l_1_p+parameters_p[2]*m_0_p
                                  +parameters_p[3]*r_1_p+parameters_p[4]*r_2_p))
            parameters = np.vstack((parameters,np.dot(inv(left), right)))
            un = np.dstack((un,un_p))
        print("finish fitting 5 parameters")
        # reshape
        parameters = parameters[1:(n_star+1),:]
        opt_flux = opt_flux[1:(n_star + 1), :]
        un = un[:,:,1:(n_star + 1)]
        self.uncertainty = un
        self.opt_flux = opt_flux

        # the shape of the uncertainty is 3*3*N

        print(parameters.shape,n_star,opt_flux.shape,un.shape)

        return opt_flux,parameters



    ##
    # CUDA version fitting parameters
    # This is a optimized version of your module.
    # use gnumpy, use CUDA

    def fitting_spectrum_parameters_single_CUDA(self,nor,ivar,inf):
        n_pixel = nor[0, :].size
        n_star = inf[:, 0].size
        one = np.ones(n_star)

        # new method for building matrix
        x_data = np.c_[one, inf]
        x_data = x_data[:, 0:n_pixel]

        y_data = inf

        z_data = np.c_[inf, one]
        z_data = z_data[:, 1:n_pixel + 1]

        # fit
        # It's not good. let's do it one star each time.

        left = np.zeros((3, 3))
        right = np.zeros(3)
        un = np.zeros((3, 3))
        parameters = np.array([0, 1, 0])
        opt_flux = np.ones(n_pixel)

        for p in range(0, n_star):

            x_data_p = x_data[p, :]
            y_data_p = y_data[p, :]
            z_data_p = z_data[p, :]
            nor_p = nor[p, :]
            ivar_p = ivar[p, :]

            # construct
            ivar_r = ivar_p.ravel()
            ni = len(ivar_r)
            print("calculating parameters", p, "{:.2f}%".format(p / n_star * 100))
            c = np.zeros((ni, ni))

            for i in range(0, ni):
                c[i, i] = ivar_r[i]

            y = nor_p.ravel()
            a = np.c_[np.c_[x_data_p.ravel(), y_data_p.ravel()], z_data_p.ravel()]

            left = np.dot(np.dot(a.T, c), a)
            right = np.dot(np.dot(a.T, c), y)

            un_p = inv(left)

            parameters_p = np.dot(inv(left), right)

            opt_flux = np.vstack(
                (opt_flux, parameters_p[0] * x_data_p + parameters_p[1] * y_data_p + parameters_p[2] * z_data_p))
            parameters = np.vstack((parameters, np.dot(inv(left), right)))
            un = np.dstack((un, un_p))
        print("finish fitting")
        # reshape
        parameters = parameters[1:(n_star + 1), :]
        opt_flux = opt_flux[1:(n_star + 1), :]
        un = un[:, :, 1:(n_star + 1)]
        self.uncertainty = un
        self.opt_flux = opt_flux

        # the shape of the uncertainty is 3*3*N

        print(parameters.shape, n_star, opt_flux.shape, un.shape)

        return opt_flux, parameters

    # Return delta_chi_squared, which should be bigger than 0
    def delta_chi_squared(self,normalzied_flux,normalized_ivar,inf_flux):
        opt_flux = self.opt_flux
        N_star = len(inf_flux[:,0])
        delta_chi = []

        for p in range(0, N_star):
            ivar_r = normalized_ivar[p, :]
            ni = len(ivar_r)

            c = np.zeros((ni, ni))
            print("Calculating delta-chi-squared",p,"{:.2f}%".format(p/N_star*100))

            for i in range(0, ni):
                c[i, i] = ivar_r[i]

            # correct chi-squared
            a_old = np.dot(np.dot(normalzied_flux[p, :] - inf_flux[p, :], c), (normalzied_flux[p, :] - inf_flux[p, :]).T)
            a_opt = np.dot(np.dot(normalzied_flux[p, :] - opt_flux[p, :], c), (normalzied_flux[p, :] - opt_flux[p, :]).T)
            delta_p = a_old-a_opt
            delta_chi.append(delta_p)
        delta_chi = np.array(delta_chi)

        return delta_chi









    def fit(self, normalized_flux, normalized_ivar, initial_labels=None,
        model_lsf=False, model_redshift=False, full_output=False, **kwargs):
        """
        Solve the labels for the given normalized fluxes and inverse variances.

        :param normalized_flux:
            A `(N_star, N_pixels)` shape of normalized fluxes that are on the 
            same dispersion scale as the trained data.

        :param normalized_ivar:
            The inverse variances of the normalized flux values. This should
            have the same shape as `normalized_flux`.

        :param initial_labels: [optional]
            The initial points to optimize from. If not given, only one
            initialization will be made from the fiducial label point.

        :param model_lsf: [optional]
            Optionally convolve the spectral model with a Gaussian broadening
            kernel of unknown width when fitting the data.

        :param model_redshift: [optional]
            Optionally redshift the spectral model when fitting the data.

        :returns:
            The labels. If `full_output` is set to True, then a three-length
            tuple of `(labels, covariance_matrix, metadata)` will be returned.
        """
        
        normalized_flux = np.atleast_2d(normalized_flux)
        normalized_ivar = np.atleast_2d(normalized_ivar)
        N_spectra = normalized_flux.shape[0]

        if initial_labels is None:
            initial_labels = self.vectorizer.fiducials
        initial_labels = np.atleast_2d(initial_labels)
        
        # Prepare the wrapper function and data.
        message = None if not kwargs.pop("progressbar", True) \
            else "Fitting {0} spectra".format(N_spectra)

        f = utils.wrapper(_fit_spectrum, 
            (self.dispersion, initial_labels, self.vectorizer, self.theta, 
                self.s2, model_lsf, model_redshift),
            kwargs, N_spectra, message=message)

        args = (normalized_flux, normalized_ivar)
        mapper = map if self.pool is None else self.pool.map

        labels, cov, metadata = zip(*mapper(f, zip(*args)))
        labels, cov = (np.array(labels), np.array(cov))

        return (labels, cov, metadata) if full_output else labels

    def fit_opt(self, normalized_flux, normalized_ivar, initial_labels=None,
            model_lsf=False, model_redshift=False, full_output=False, **kwargs):
        """
        Solve the labels for the given normalized fluxes and inverse variances.

        :param normalized_flux:
            A `(N_star, N_pixels)` shape of normalized fluxes that are on the
            same dispersion scale as the trained data.

        :param normalized_ivar:
            The inverse variances of the normalized flux values. This should
            have the same shape as `normalized_flux`.

        :param initial_labels: [optional]
            The initial points to optimize from. If not given, only one
            initialization will be made from the fiducial label point.

        :param model_lsf: [optional]
            Optionally convolve the spectral model with a Gaussian broadening
            kernel of unknown width when fitting the data.

        :param model_redshift: [optional]
            Optionally redshift the spectral model when fitting the data.

        :returns:
            The labels. If `full_output` is set to True, then a three-length
            tuple of `(labels, covariance_matrix, metadata)` will be returned.
        """

        normalized_flux = np.atleast_2d(normalized_flux)
        normalized_ivar = np.atleast_2d(normalized_ivar)
        N_spectra = normalized_flux.shape[0]

        if initial_labels is None:
            initial_labels = self.vectorizer.fiducials
        initial_labels = np.atleast_2d(initial_labels)

        # Prepare the wrapper function and data.
        message = None if not kwargs.pop("progressbar", True) \
            else "Fitting {0} spectra".format(N_spectra)

        # add something
        inferred_labels = self.fit_labelled_set()
        inf = np.dot(self.theta, self.vectorizer(inferred_labels).T).T

        opt_flux,theta_opt,parameters = self.fitting_spectrum_parameters(normalized_flux,normalized_ivar,inf)

        f = utils.wrapper(_fit_spectrum,
                          (self.dispersion, initial_labels, self.vectorizer, theta_opt,
                           self.s2, model_lsf, model_redshift),
                          kwargs, N_spectra, message=message)

        args = (normalized_flux, normalized_ivar)
        mapper = map if self.pool is None else self.pool.map
        print("OPT")

        labels, cov, metadata = zip(*mapper(f, zip(*args)))
        labels, cov = (np.array(labels), np.array(cov))

        return (labels, cov, metadata) if full_output else labels


    @model.requires_training_wheels
    def _set_s2_by_hogg_heuristic(self):
        """
        Set the pixel scatter by Hogg's heuristic.

        See https://github.com/andycasey/AnniesLasso_2/issues/31 for more details.
        """

        model_flux = self.predict(self.labels_array)
        residuals_squared = (model_flux - self.normalized_flux)**2

        def objective_function(s, residuals_squared, ivar):
            adjusted_ivar = ivar/(1. + ivar * s**2)
            chi_sq = residuals_squared * adjusted_ivar
            return (np.mean(chi_sq) - 1.0)**2

        s = []
        for j in range(self.dispersion.size):
            s.append(op.fmin(objective_function, 0,
                args=(residuals_squared[:, j], self.normalized_ivar[:, j]), 
                disp=False))

        self.s2 = np.array(s)**2
        return True


def _estimate_label_vector(theta, s2, normalized_flux, normalized_ivar,
    **kwargs):
    """
    Perform a matrix inversion to estimate the values of the label vector given
    some normalized fluxes and associated inverse variances.

    :param theta:
        The theta coefficients obtained from the training phase.

    :param s2:
        The intrinsic pixel variance.

    :param normalized_flux:
        The normalized flux values. These should be on the same dispersion scale
        as the labelled data set.

    :param normalized_ivar:
        The inverse variance of the normalized flux values. This should have the
        same shape as `normalized_flux`.
    """

    inv_var = normalized_ivar/(1. + normalized_ivar * s2)
    A = np.dot(theta.T, inv_var[:, None] * theta)
    B = np.dot(theta.T, inv_var * normalized_flux)
    return np.linalg.solve(A, B)


def _fit_spectrum(normalized_flux, normalized_ivar, dispersion, initial_labels, 
    vectorizer, theta, s2, model_lsf=False, model_redshift=False, **kwargs):
    """
    Fit a single spectrum by least-squared fitting.
    
    :param normalized_flux:
        The normalized flux values.

    :param normalized_ivar:
        The inverse variance array for the normalized fluxes.

    :param dispersion:
        The dispersion (e.g., wavelength) points for the normalized fluxes.

    :param initial_labels:
        The point(s) to initialize optimization from.

    :param vectorizer:
        The vectorizer to use when fitting the data.

    :param theta:
        The theta coefficients (spectral derivatives) of the trained model.

    :param s2:
        The pixel scatter (s^2) array for each pixel.

    :param model_lsf: [optional]
        Convolve the spectral model with a Gaussian kernel at fitting time.

    :param model_redshift: [optional]
        Allow for a residual redshift in the spectral model at fitting time.
    """

    adjusted_ivar = normalized_ivar/(1. + normalized_ivar * s2)
    adjusted_sigma = np.sqrt(1.0/adjusted_ivar)
    
    # Exclude non-finite points (e.g., points with zero inverse variance 
    # or non-finite flux values, but the latter shouldn't exist anyway).
    use = np.isfinite(adjusted_sigma * normalized_flux)
    N_labels = vectorizer.scales.size
    
    if not np.any(use):
        logger.warn("No information in spectrum!")
        return (np.nan * np.ones(N_labels), None, {
                "fail_message": "Pixels contained no information"})

    normalized_flux = normalized_flux[use]
    adjusted_sigma = adjusted_sigma[use]

    max_abs_velocity = abs(kwargs.get("max_abs_velocity", 10))
    
    # Check the vectorizer whether it has a derivative built in.
    if kwargs.get("Dfun", False):
        try:
            vectorizer.get_label_vector_derivative(vectorizer.fiducials)
        
        except NotImplementedError:
            Dfun = None
            logger.debug("No label vector derivative available!")
            
        except:
            logger.exception("Exception raised when trying to calculate the "
                             "label vector derivative at the fiducial values:")
            raise

        else:
            # Use the label vector derivative.
            """
            # Presumably because of the way leastsq works, the adjusted_inv_sigma
            # does not enter here, otherwise we get incorrect results.
            Dfun = lambda xdata, l: \
                np.dot(theta, vectorizer.get_label_vector_derivative(*l)).T[use]
            """
            raise NotImplementedError("requires a thinko")

            def Dfun(labels, xdata, ydata, f, adjusted_inv_sigma):
                return np.dot(theta, 
                    vectorizer.get_label_vector_derivative(labels)).T[:, use]
    else:
        Dfun = None

    mean_pixel_scale = 1.0/np.diff(dispersion).mean() # px/Angstrom

    def f(xdata, *parameters):

        y = np.dot(theta, vectorizer(parameters[:N_labels]).T)[:, 0]

        # Convolve?
        if model_lsf:
            # This will always be the last parameter.
            y = gaussian_filter(y, abs(parameters[-1]) * mean_pixel_scale)
            
        # Redshift?
        if model_redshift:
            index = -2 if model_lsf else -1
            v = parameters[index]
            
            if np.abs(v) >= max_abs_velocity:
                logger.debug("Returning NaNs because outside of max velocity")
                return np.nan * np.ones(sum(use))

            y = np.interp(dispersion, 
                dispersion * (1 + v/299792.458), y,
                left=np.nan, right=np.nan)

        return y[use]


    kwds = {
        "f": f,
        "xdata": None,
        "ydata": normalized_flux,
        "sigma": adjusted_sigma,
        "absolute_sigma": True,

        # These get passed through to leastsq:
        "Dfun": Dfun,
        "col_deriv": True,
        "ftol": 7./3 - 4./3 - 1, # Machine precision.
        "xtol": 7./3 - 4./3 - 1, # Machine precision.
        "gtol": 0.0,
        "maxfev": 100000, # MAGIC
        "epsfcn": None,
        "factor": 0.1, # Smallest step size available for gradient approximation
        "diag": 1.0/vectorizer.scales
    }

    # Only update the keywords with things that op.curve_fit/op.leastsq expects.
    for key in set(kwargs).intersection(kwds):
        if key == "Dfun": continue
        kwds[key] = kwargs[key]


    results = []
    for p0 in np.atleast_2d(initial_labels):
        kwds["p0"] = list(p0)
        
        if model_redshift:
            kwds["p0"] += [0]
        
        if model_lsf:
            kwds["p0"] += [5] # MAGIC
        
        try:
            op_labels, cov = op.curve_fit(**kwds)
        
        except RuntimeError:
            logger.exception("Exception in fitting from {}".format(p0))
            continue

        fvec = f(None, *op_labels)

        meta = {
            "p0": kwds["p0"],
            "fvec": fvec,
            "chi_sq": np.sum((fvec - normalized_flux)**2 / adjusted_sigma**2),
        }
        results.append((op_labels, cov, meta))

    if len(results) == 0:
        logger.warn("No results found!")
        return (np.nan * np.ones(N_labels), None, {"fail_message": "No results found"})

    best_result_index = np.nanargmin([m["chi_sq"] for (o, c, m) in results])
    op_labels, cov, meta = results[best_result_index]

    if np.allclose(op_labels, meta["p0"]):
        logger.warn("Discarding optimized result because it is the same as the "
            "initial value!")

        # We are in dire straits. We should not trust the result.
        op_labels *= np.nan

    if not np.any(np.isfinite(cov)):
        logger.warn("Non-finite covariance matrix returned!")
        
    # Defaults for LSF/redshift parameters
    meta.update(kernel=0, redshift=0)
    for key, effect in zip(("kernel", "redshift"), (model_lsf, model_redshift)):
        if effect:
            meta[key] = op_labels[-1]
            op_labels = op_labels[:-1]
    
    # Save additional information.
    meta.update({
        "kernel": abs(meta["kernel"]),
        "label_names": vectorizer.label_names,
        "best_result_index": best_result_index,
        "method": "curve_fit",
        "derivatives_used": Dfun is not None,
        "snr": np.nanmedian(normalized_flux * np.sqrt(normalized_ivar[use])),
        "r_chi_sq": meta["chi_sq"]/(use.sum() - len(vectorizer.fiducials) - 1),
        "model_flux": np.dot(theta, vectorizer(op_labels).T).flatten(),
    })
    for key in ("ftol", "xtol", "gtol", "maxfev", "factor", "epsfcn"):
        meta[key] = kwds[key]
    
    return (op_labels, cov, meta)


def _fit_pixel(initial_theta, initial_s2, normalized_flux, normalized_ivar, 
    design_matrix, fixed_scatter, **kwargs):
    """
    Return the optimal model coefficients and pixel scatter given the normalized
    flux, the normalized inverse variance, and the design matrix.

    :param initial_theta:
        The initial model coefficients to optimize from.

    :param initial_s2:
        The initial pixel scatter (s^2) terms to optimize from (if fixed_scatter
        is False).

    :param normalized_flux:
        The normalized flux values for a given pixel, from all stars.

    :param normalized_ivar:
        The inverse variance of the normalized flux values for a given pixel,
        from all stars.

    :param design_matrix:
        The design matrix for the spectral model.

    :param fixed_scatter:
        Keep the pixel scatter term fixed.

    :returns:
        The optimised label vector coefficients and scatter for this pixel, even
        if it was supplied by the user.
    """

    design_matrix = utils._unpack_value(design_matrix)

    raise a
    # This initial theta will also be returned if we have no valid fluxes.
    initial_theta = np.hstack([1, np.zeros(design_matrix.shape[1] - 1)])

    if np.all(normalized_ivar == 0):
        return np.hstack([initial_theta, scatter if fixed_scatter else 0])

    # Optimize the parameters.
    kwds = {
        "maxiter": np.inf,
        "maxfun": np.inf,
        "disp": False,
        "full_output": True
    }
    kwds.update(kwargs.get("op_kwargs", {}))
    args = (normalized_flux, normalized_ivar, design_matrix)    
    logger.debug("Optimizer kwds: {}".format(kwds))

    if fixed_scatter:
        p0 = initial_theta
        func = _model_pixel_fixed_scatter
        args = tuple([scatter] + list(args))

    else:
        p0 = np.hstack([initial_theta, p0_scatter])
        func = _model_pixel

    op_params, fopt, direc, n_iter, n_funcs, warnflag = op.fmin_powell(
        func, p0, args=args, **kwds)

    if warnflag > 0:
        logger.warning("Warning: {}".format([
            "Maximum number of function evaluations made during optimisation.",
            "Maximum number of iterations made during optimisation."
            ][warnflag - 1]))

    return np.hstack([op_params, scatter]) if fixed_scatter else op_params




def _model_pixel(theta, scatter, normalized_flux, normalized_ivar,
    design_matrix, **kwargs):

    inv_var = normalized_ivar/(1. + normalized_ivar * scatter**2)
    return model._chi_sq(theta, design_matrix, normalized_flux, inv_var) 


def _model_pixel_fixed_scatter(parameters, normalized_flux, normalized_ivar,
    design_matrix, **kwargs):
    
    theta, scatter = parameters[:-1], parameters[-1]
    return _model_pixel(
        theta, scatter, normalized_flux, normalized_ivar, design_matrix)


def _fit_pixel_with_fixed_scatter(scatter, normalized_flux, normalized_ivar,
    design_matrix, **kwargs):
    """
    Fit the normalized flux for a single pixel (across many stars) given some
    pixel variance term, and return the best-fit theta coefficients.

    :param scatter:
        The additional scatter to adopt in the pixel.

    :param normalized_flux:
        The normalized flux values for a single pixel across many stars.

    :param normalized_ivar:
        The inverse variance of the normalized flux values for a single pixel
        across many stars.

    :param design_matrix:
        The design matrix for the model.
    """

    theta, ATCiAinv, inv_var = _fit_theta(normalized_flux, normalized_ivar,
        scatter**2, design_matrix)

    return_theta = kwargs.get("__return_theta", False)
    if ATCiAinv is None:
        return 0.0 if not return_theta else (0.0, theta)

    # We take inv_var back from _fit_theta because it is the same quantity we 
    # need to calculate, and it saves us one operation.
    Q   = model._chi_sq(theta, design_matrix, normalized_flux, inv_var) 
    return (Q, theta) if return_theta else Q


def _fit_theta(normalized_flux, normalized_ivar, s2, design_matrix):
    """
    Fit theta coefficients to a set of normalized fluxes for a single pixel.

    :param normalized_flux:
        The normalized fluxes for a single pixel (across many stars).

    :param normalized_ivar:
        The inverse variance of the normalized flux values for a single pixel
        across many stars.

    :param scatter:
        The additional scatter to adopt in the pixel.

    :param design_matrix:
        The model design matrix.

    :returns:
        The label vector coefficients for the pixel, the inverse variance matrix
        and the total inverse variance.
    """

    ivar = normalized_ivar/(1. + normalized_ivar * s2)
    CiA = design_matrix * np.tile(ivar, (design_matrix.shape[1], 1)).T
    try:
        ATCiAinv = np.linalg.inv(np.dot(design_matrix.T, CiA))
    except np.linalg.linalg.LinAlgError:
        #if logger.getEffectiveLevel() == logging.DEBUG: raise
        return (np.hstack([1, [0] * (design_matrix.shape[1] - 1)]), None, ivar)

    ATY = np.dot(design_matrix.T, normalized_flux * ivar)
    theta = np.dot(ATCiAinv, ATY)

    return (theta, ATCiAinv, ivar)

