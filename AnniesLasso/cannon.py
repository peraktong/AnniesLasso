#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
A pedestrian version of The Cannon.
"""

from __future__ import (division, print_function, absolute_import,
                        unicode_literals)

__all__ = ["CannonModel"]

import cPickle as pickle
import logging
import numpy as np
import scipy.optimize as op
import tempfile
import os
from six import string_types

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
    def train(self, fixed_scatter=False, progressbar=True, initial_theta=None,
        use_neighbouring_pixel_theta=False,
        **kwargs):
        """
        Train the model based on the labelled set.
        """
        
        logger.warn("OVERWRITING S2 AND FIXED SCATTER")
        self.s2 = 0.0
        fixed_scatter = True


        if fixed_scatter and self.s2 is None:
            raise ValueError("intrinsic pixel variance (s2) must be set "
                             "before training if fixed_scatter is set to True")

        # Initialize the scatter.
        p0_scatter = np.sqrt(self.s2) if fixed_scatter \
            else 0.01 * np.ones_like(self.dispersion)

        # Prepare details about any progressbar to show.
        M, N = self.normalized_flux.shape
        message = None if not progressbar else \
            "Training {0}-label {1} with {2} stars and {3} pixels/star".format(
                len(self.vectorizer.label_names), type(self).__name__, M, N)

        # Prepare the method and arguments.
        fitter = kwargs.pop("function", _fit_pixel)
        kwds = {
            "fixed_scatter": fixed_scatter,
            "op_kwargs": kwargs.pop("op_kwargs", {}),
            "op_bfgs_kwargs": kwargs.pop("op_bfgs_kwargs", {})
        }
        #kwds.update(kwargs)

        temporary_filenames = []

        args = [self.normalized_flux.T, self.normalized_ivar.T, p0_scatter]
        args.extend(kwargs.get("additional_args", []))

        pixel_metadata = []
        if self.pool is None:
            mapper = map
            
            # Single threaded, so we can supply a large design matrix.            
            kwds["design_matrix"] = self.design_matrix

            results = []
            previous_theta = [None]
            for j, row in enumerate(utils.progressbar(zip(*args), message=message)):
                if j > 0 and use_neighbouring_pixel_theta:
                    row = list(row)
                    row[-1] = previous_theta[-1]
                    row = tuple(row)
                #row = list(row)
                #raise a
                #row[-1] = initial_theta
                #row = tuple(row)
                #print("ACTUALLY SENDING {}".format(initial_theta))
                result, metadata = fitter(*row, **kwds)
                results.append(result)
                pixel_metadata.append(metadata)
                if use_neighbouring_pixel_theta:
                    previous_theta[-1] = results[-1][:-1]

                logger.debug("Theta: {}".format(results[-1][:-1]))

            results = np.array(results)

        else:
            mapper = self.pool.map
            
            # Write the design matrix to a temporary file.
            _, temporary_filename = tempfile.mkstemp()
            with open(temporary_filename, "wb") as fp:
                pickle.dump(self.design_matrix, fp, -1)
            kwds["design_matrix"] = temporary_filename
            temporary_filenames.append(temporary_filename)

            # Wrap the function so we can parallelize it out.
            try:
                f = utils.wrapper(fitter, None, kwds, N, message=message)
                output = mapper(f, [row for row in zip(*args)])

            except KeyboardInterrupt:
                logger.debug("Removing temporary filenames:\n{}".format(
                    "\n".join(temporary_filenames)))
                map(os.remove, temporary_filenames)

            else:
                results = []
                metadata = []
                for r, m in output:
                    results.append(r)
                    metadata.append(m)

                results = np.array(results)

        #self.theta = theta
        #self.s2 = scatter**2

        # Clean up any temporary files.
        for filename in temporary_filenames:
            if os.path.exists(filename): os.remove(filename)

        # Unpack the results.
        self.theta, self.s2 = (results[:, :-1], results[:, -1]**2)

        assert np.all(self.s2 == 0.0)
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
    def fit(self, normalized_flux, normalized_ivar, full_output=False, **kwargs):
        """
        Solve the labels for the given normalized fluxes and inverse variances.

        :param normalized_flux:
            The normalized fluxes. These should be on the same dispersion scale
            as the trained data.

        :param normalized_ivar:
            The inverse variances of the normalized flux values. This should
            have the same shape as `normalized_flux`.

        :returns:
            The labels.
        """
        print("OK IN")
        normalized_flux = np.atleast_2d(normalized_flux)
        normalized_ivar = np.atleast_2d(normalized_ivar)

        # Prepare the wrapper function and data.
        N_spectra = normalized_flux.shape[0]
        message = None if not kwargs.pop("progressbar", True) \
            else "Fitting {0} spectra".format(N_spectra)
        kwds = {
            "vectorizer": self.vectorizer,
            "theta": self.theta,
            "s2": self.s2
        }
        args = [normalized_flux, normalized_ivar]
        #if self.pool is None:

        f = utils.wrapper(_fit_spectrum_bfgs, None, kwds, N_spectra, message=message)

        # Do the grunt work.
        mapper = map if self.pool is None else self.pool.map

        # Do a test run first?
        #labels, cov = map(np.array, zip(*mapper(f, [r for r in zip(*args)[:1]])))



        labels, cov = map(np.array, zip(*mapper(f, [r for r in zip(*args)])))
        #labels = np.array(mapper(f, [r for r in zip(*args)]))
        #return labels
        return (labels, cov) if full_output else labels

        #return (labels) if kwargs.get("full_output", False) else labels


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



def _fit_spectrum_bfgs(normalized_flux, normalized_ivar, vectorizer, theta, s2,
    **kwargs):
    
    adjusted_ivar = normalized_ivar/(1. + normalized_ivar * s2)
    #use = np.isfinite(adjusted_ivar * normalized_flux)

    #t = theta[use]
    #flux = normalized_flux[use]
    #adjusted_ivar = adjusted_ivar #np.sqrt(adjusted_ivar)#[use])
    inv_sigma = np.sqrt(adjusted_ivar)

    def objective(labels):
        m = np.dot(theta, vectorizer(labels).T).flatten()
        residual = (m - normalized_flux)
        #f = adjusted_ivar * residual**2
        #print(labels, f.sum())
        #return f.sum()
        f = inv_sigma * residual
        #print(labels, f.sum())
        return f

    # Check the vectorizer whether it has a derivative built in.
    try:
        vectorizer.get_label_vector_derivative(vectorizer.fiducials)
    
    except NotImplementedError:
        logger.debug("No label vector derivative available!")
        Dfun = None

    except:
        logger.exception("Exception raised when trying to calculate the label "
                         "vector derivative at the fiducial values:")
        raise

    else:
        # Use the label vector derivative.
        def Dfun(labels):
            g = np.dot(theta, vectorizer.get_label_vector_derivative(labels)[0])
            return inv_sigma * g.T

        def gradient(labels):
            m = np.dot(theta, vectorizer(labels).T).flatten()
            residual = (m - normalized_flux)
            g = np.dot(theta, vectorizer.get_label_vector_derivative(labels)[0])

            return 2.0 * np.dot(g.T, adjusted_ivar * residual)

    # MAGIC: GET A GOOD GUESS OF THE PARAMS.
    kwds = {
        "f": lambda _, *labels: np.dot(theta, vectorizer(list(labels) + [labels[-1]] * 14).T).flatten(),
        "xdata": None, # theta is already available.
        "ydata": normalized_flux,
        "p0": np.array(vectorizer.fiducials[:3], dtype=float),
        "sigma": adjusted_ivar,
        "absolute_sigma": False,
        #"check_finite": True,
    }
    kwds.update({ k: v for k, v in kwargs.items() if k in kwds })
    
    initial, cov = op.curve_fit(**kwds)
    
    initial = np.array(list(initial) + [initial[-1]] * 14)

    kwds = {
        "func": objective,
        "x0": initial, #np.array(vectorizer.fiducials.copy(), dtype=float),
        "args": (),
        "Dfun": None,
        "col_deriv": True,
        "ftol": 7./3 - 4./3 - 1, # Machine precision.
        "xtol": 7./3 - 4./3 - 1, # Machine precision.
        "gtol": 0.0,
        "maxfev": 10**8,
        "epsfcn": None,
        "factor": 0.1,
        "diag": vectorizer.scales
    }
    # Only update the keywords with things that op.leastsq expects.
    kwds.update({ k: v for k, v in kwargs.items() if k in kwds })

    op_labels, cov, info, message, ier = op.leastsq(full_output=True, **kwds)

    if ier not in range(1, 5):
        logger.warning("Least-sq result was {0}: {1}".format(ier, message))
        raise WhoaYouWannaKnowAboutThis

    return (op_labels, cov)
    """

    """

    kwds = {
        "func": objective,
        "x0": initial, #np.array(vectorizer.fiducials.copy(), dtype=float),
        "fprime": gradient,
        "args": (),
        "approx_grad": False,
        "bounds": None,
        "m": 10,
        "factr": 0.1,
        "pgtol": 1e-6,
        "epsilon": 1e-8,
        "iprint": -1,
        "disp": 0,
        "maxfun": np.inf,
        "maxiter": np.inf,
        "callback": None,
    }
    # Only update the keywords with things that op.leastsq expects.
    kwds.update({ k: v for k, v in kwargs.items() if k in kwds })

    op_labels, fopt, info = op.fmin_l_bfgs_b(**kwds)

    if info["warnflag"] > 0:
        logger.warning("BFGS stopped prematurely: {}".format(info["task"]))
    
        kwds = {
            "func": objective,
            "x0": op_labels,
            "args": (),
            "xtol": 1e-6,
            "ftol": 1e-6,
            "maxiter": 10**8,
            "maxfun": 10**8,
            "disp": False,
            "retall": False
        }
        # Only update the keywords with things that op.leastsq expects.
        kwds.update({ k: v for k, v in kwargs.items() if k in kwds })

        #op_labels, fopt, direc, n_iter, n_funcs, warnflag = op.fmin_powell(
        #    full_output=True, **kwds)
        op_labels, fopt, n_iter, n_funcs, warnflag = op.fmin(full_output=True,
            **kwds)

        if warnflag > 0:
            logger.warn("Powell optimization failed: {}".format([
                    "MAXIMUM NUMBER OF FUNCTION EVALUATIONS.",
                    "MAXIMUM NUMBER OF ITERATIONS."
                ][warnflag - 1]))
        else:
            logger.info("Powell optimization completed successfully.")

        metadata = {}
        metadata.update({
            "fmin_fopt": fopt,
            "fmin_niter": n_iter,
            "fmin_nfuncs": n_funcs,
            "fmin_warnflag": warnflag
        })

    return (op_labels, fopt)
    """

    def f(xdata, *labels):
        return np.dot(theta, vectorizer(labels).T).flatten()
        #print(labels, f.sum())
        #return f
        

    kwds = {
        "f": lambda _, *labels: np.dot(theta, vectorizer(labels).T).flatten(),
        "xdata": None, # theta is already available.
        "ydata": normalized_flux,
        #"p0": np.array(vectorizer.fiducials.copy(), dtype=float),
        "p0": np.array([  4.54917822e+03, 2.36721921e+00, 1.15975127e-01, 3.03657055e-02
, 9.72300023e-03 ,9.25753042e-02,-1.13341119e-02,5.66763096e-02
, 2.43287757e-01,3.71136330e-02,5.40449992e-02,3.48223984e-01
, 1.09878577e-01,2.43512809e-01,2.12157130e-01,5.76438233e-02,
   -1.01278335e-01]),
        "sigma": adjusted_ivar,
        "absolute_sigma": False,
        #"check_finite": True,
    }
    kwds.update({ k: v for k, v in kwargs.items() if k in kwds })
    
    op_labels, cov = op.curve_fit(**kwds)
    print(op_labels)
    return (op_labels, cov)
    """




def _fit_spectrum(normalized_flux, normalized_ivar, vectorizer, theta, s2,
    **kwargs):
    """
    Solve the labels for given pixel fluxes and uncertainties for a single star.

    :param normalized_flux:
        The normalized fluxes. These should be on the same dispersion scale
        as the trained data.

    :param normalized_ivar:
        The 1-sigma uncertainties in the fluxes. This should have the same
        shape as `normalized_flux`.

    :param vectorizer:
        The model vectorizer.

    :param theta:
        The theta coefficients obtained from the training phase.

    :param s2:
        The intrinsic pixel variance.

    :returns:
        The labels and covariance matrix.
    """

    """
    # TODO: Re-visit this.
    # Get an initial estimate of the label vector from a matrix inversion,
    # and then ask the vectorizer to interpret that label vector into the 
    # (approximate) values of the labels that could have produced that 
    # label vector.
    lv = _estimate_label_vector(theta, s2, normalized_flux, normalized_ivar)
    initial = vectorizer.get_approximate_labels(lv)
    """

    # Overlook the bad pixels.
    inv_var = normalized_ivar/(1. + normalized_ivar * s2)
    use = np.isfinite(inv_var * normalized_flux)

    kwds = {
        "p0": vectorizer.fiducials,
        "maxfev": 10**6,
        "sigma": inv_var[use],
    }
    kwds.update(kwargs)
    
    f = lambda t, *l: np.dot(t, vectorizer(l).T).flatten()
    labels, cov = op.curve_fit(f, theta[use], normalized_flux[use], **kwds)
    return (labels, cov)





def _fit_spectrum_fmin_powell(normalized_flux, normalized_ivar, vectorizer, theta, s2,
    **kwargs):
    """
    Solve the labels for given pixel fluxes and uncertainties for a single star.

    :param normalized_flux:
        The normalized fluxes. These should be on the same dispersion scale
        as the trained data.

    :param normalized_ivar:
        The 1-sigma uncertainties in the fluxes. This should have the same
        shape as `normalized_flux`.

    :param vectorizer:
        The model vectorizer.

    :param theta:
        The theta coefficients obtained from the training phase.

    :param s2:
        The intrinsic pixel variance.

    :returns:
        The labels and covariance matrix.
    """

    """
    # TODO: Re-visit this.
    # Get an initial estimate of the label vector from a matrix inversion,
    # and then ask the vectorizer to interpret that label vector into the 
    # (approximate) values of the labels that could have produced that 
    # label vector.
    lv = _estimate_label_vector(theta, s2, normalized_flux, normalized_ivar)
    initial = vectorizer.get_approximate_labels(lv)
    """

    # Overlook the bad pixels.
    inv_var = normalized_ivar/(1. + normalized_ivar * s2)
    use = np.isfinite(inv_var * normalized_flux)

    flux = normalized_flux[use]
    ivar = normalized_ivar[use]

    # y = (theta * lv - m)**2 * inv_var
    # dy/dtheta = 

    def objective(labels):
        m = np.dot(theta, vectorizer(labels).T).flatten()
        stuff = np.sum(ivar * (flux - m[use])**2)
        print(labels, stuff)
        return stuff

    return op.fmin_powell(objective, kwargs.get("p0", vectorizer.fiducials),
        xtol=1e-6, ftol=1e-6)




def _fit_spectrum_leastsq(normalized_flux, normalized_ivar, vectorizer, theta, s2,
    **kwargs):
    """
    Solve the labels for given pixel fluxes and uncertainties for a single star.

    :param normalized_flux:
        The normalized fluxes. These should be on the same dispersion scale
        as the trained data.

    :param normalized_ivar:
        The 1-sigma uncertainties in the fluxes. This should have the same
        shape as `normalized_flux`.

    :param vectorizer:
        The model vectorizer.

    :param theta:
        The theta coefficients obtained from the training phase.

    :param s2:
        The intrinsic pixel variance.

    :returns:
        The labels and covariance matrix.
    """

    """
    # TODO: Re-visit this.
    # Get an initial estimate of the label vector from a matrix inversion,
    # and then ask the vectorizer to interpret that label vector into the 
    # (approximate) values of the labels that could have produced that 
    # label vector.
    lv = _estimate_label_vector(theta, s2, normalized_flux, normalized_ivar)
    initial = vectorizer.get_approximate_labels(lv)
    """

    # Overlook the bad pixels.
    inv_var = normalized_ivar/(1. + normalized_ivar * s2)
    use = np.isfinite(inv_var * normalized_flux)

    flux = normalized_flux[use]
    inv_sigma = np.sqrt(normalized_ivar[use])

    def objective(labels):
        print(labels)
        m = np.dot(theta, vectorizer(labels).T).flatten()
        return (flux - m[use])

    # leastsq uses:
    # x = arg min(sum(func(y)**2, axis=0))
    #          y
    # so our func should be (delta/sqrt(ivar))

    return op.leastsq(objective, kwargs.get("p0", vectorizer.fiducials),
        maxfev=10**6, xtol=1e-6, ftol=1e-6)





def _fit_spectrum_fmin(normalized_flux, normalized_ivar, vectorizer, theta, s2,
    **kwargs):
    """
    Solve the labels for given pixel fluxes and uncertainties for a single star.

    :param normalized_flux:
        The normalized fluxes. These should be on the same dispersion scale
        as the trained data.

    :param normalized_ivar:
        The 1-sigma uncertainties in the fluxes. This should have the same
        shape as `normalized_flux`.

    :param vectorizer:
        The model vectorizer.

    :param theta:
        The theta coefficients obtained from the training phase.

    :param s2:
        The intrinsic pixel variance.

    :returns:
        The labels and covariance matrix.
    """

    """
    # TODO: Re-visit this.
    # Get an initial estimate of the label vector from a matrix inversion,
    # and then ask the vectorizer to interpret that label vector into the 
    # (approximate) values of the labels that could have produced that 
    # label vector.
    lv = _estimate_label_vector(theta, s2, normalized_flux, normalized_ivar)
    initial = vectorizer.get_approximate_labels(lv)
    """

    # Overlook the bad pixels.
    inv_var = normalized_ivar/(1. + normalized_ivar * s2)
    use = np.isfinite(inv_var * normalized_flux)

    ivar = normalized_ivar[use]
    flux = normalized_flux[use]
    t = theta[use]

    def objective(labels):
        m = np.dot(t, vectorizer(labels).T).flatten()
        f = np.sum(normalized_ivar * (normalized_flux - m)**2)
        #print(labels, f)
        return f

    return op.fmin(objective, vectorizer.fiducials, disp=False, maxfun=np.inf,
        maxiter=np.inf, xtol=1e-6, ftol=1e-6)

    kwds = {
        "p0": vectorizer.fiducials,
        "maxfev": 10**6,
        "sigma": ivar,
    }
    kwds.update(kwargs)
    
    #f = lambda t, *l: np.dot(t, vectorizer(l).T).flatten()
    def f(t, *l):
        f = np.dot(t, vectorizer(l).T).flatten()
        #print(l)
        return f
    labels, cov = op.curve_fit(f, t, flux, **kwds)
    return (labels, cov)

def _fit_pixel(normalized_flux, normalized_ivar, scatter, design_matrix,
    fixed_scatter=False, **kwargs):
    """
    Return the optimal vectorizer coefficients and variance term for a pixel
    given the normalized flux, the normalized inverse variance, and the design
    matrix.

    :param normalized_flux:
        The normalized flux values for a given pixel, from all stars.

    :param normalized_ivar:
        The inverse variance of the normalized flux values for a given pixel,
        from all stars.

    :param design_matrix:
        The design matrix for the spectral model.

    :param scatter:
        Fit the data using a fixed scatter term. If this value is set to None,
        then the scatter will be calculated.

    :returns:
        The optimised label vector coefficients and scatter for this pixel, even
        if it was supplied by the user.
    """

    if isinstance(design_matrix, string_types):
        with open(design_matrix, "rb") as fp:
            design_matrix = pickle.load(fp)

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


def _fit_pixel_s2_theta_separately(normalized_flux, normalized_ivar, scatter, design_matrix,
    fixed_scatter=False, **kwargs):

    """
    theta, ATCiAinv, inv_var = _fit_theta(normalized_flux, normalized_ivar,
        scatter, design_matrix)

    # Singular matrix or fixed scatter?
    if ATCiAinv is None or fixed_scatter:
        return np.hstack([theta, scatter if fixed_scatter else 0.0])

    # Optimise the pixel scatter, and at each pixel scatter value we will 
    # calculate the optimal vector coefficients for that pixel scatter value.
    kwds = {
        "maxiter": np.inf,
        "maxfun": np.inf,
        "disp": False, 
        "full_output":True

    }
    kwds.update(kwargs.get("op_kwargs", {}))
    logger.info("Passing to optimizer: {}".format(kwds))

    op_scatter, fopt, direc, n_iter, n_funcs, warnflag = op.fmin_powell(
        _fit_pixel_with_fixed_scatter, scatter,
        args=(normalized_flux, normalized_ivar, design_matrix),
        **kwds)

    if warnflag > 0:
        logger.warning("Warning: {}".format([
            "Maximum number of function evaluations made during optimisation.",
            "Maximum number of iterations made during optimisation."
            ][warnflag - 1]))

    theta, ATCiAinv, inv_var = _fit_theta(normalized_flux, normalized_ivar,
        op_scatter, design_matrix)
    return np.hstack([theta, op_scatter])
    """


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
        scatter, design_matrix)

    return_theta = kwargs.get("__return_theta", False)
    if ATCiAinv is None:
        return 0.0 if not return_theta else (0.0, theta)

    # We take inv_var back from _fit_theta because it is the same quantity we 
    # need to calculate, and it saves us one operation.
    Q   = model._chi_sq(theta, design_matrix, normalized_flux, inv_var) 
    return (Q, theta) if return_theta else Q


def _fit_theta(normalized_flux, normalized_ivar, scatter, design_matrix):
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

    ivar = normalized_ivar/(1. + normalized_ivar * scatter**2)
    CiA = design_matrix * np.tile(ivar, (design_matrix.shape[1], 1)).T
    try:
        ATCiAinv = np.linalg.inv(np.dot(design_matrix.T, CiA))
    except np.linalg.linalg.LinAlgError:
        #if logger.getEffectiveLevel() == logging.DEBUG: raise
        return (np.hstack([1, [0] * (design_matrix.shape[1] - 1)]), None, ivar)

    ATY = np.dot(design_matrix.T, normalized_flux * ivar)
    theta = np.dot(ATCiAinv, ATY)

    return (theta, ATCiAinv, ivar)

