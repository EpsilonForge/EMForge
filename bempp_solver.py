import bempp.api
import numpy as np
from bempp.api.operators.boundary.maxwell import multitrace_operator
import pyvista as pv

bempp.api.enable_console_logging()

def plane_wave(k, polarization, direction, point):
    return polarization * np.exp(1j * k * np.dot(point, direction))


def solve(meshfile, frequency, eps_r, mu_r, theta, nx, ny, x_a, x_b, y_a, y_b):

    scatterer = bempp.api.import_grid(meshfile)

    vacuum_permittivity = 8.854187817E-12
    vacuum_permeability = 4 * np.pi * 1E-7

    k_ext = 2 * np.pi * frequency * np.sqrt(vacuum_permittivity * vacuum_permeability)
    k_int = k_ext * np.sqrt(eps_r * mu_r)

    direction = np.array([np.cos(theta), np.sin(theta), 0])
    polarization = np.array([0, 0, 1.0])

    @bempp.api.complex_callable
    def tangential_trace(point, n, domain_index, result):
        value = polarization * np.exp(1j * k_ext * np.dot(point, direction))
        result[:] =  np.cross(value, n)

    @bempp.api.complex_callable
    def neumann_trace(point, n, domain_index, result):
        value = np.cross(direction, polarization) * 1j * k_ext * np.exp(1j * k_ext * np.dot(point, direction))
        result[:] =  1./ (1j * k_ext) * np.cross(value, n)

    A0_int = multitrace_operator(
        scatterer, k_int, epsilon_r=eps_r, mu_r=mu_r, space_type='all_rwg', assembler="dense", device_interface="numba")
    A0_ext = multitrace_operator(
        scatterer, k_ext, space_type='all_rwg', assembler="dense", device_interface="numba")

    A = A0_int + A0_ext
    rhs = [bempp.api.GridFunction(space=A.range_spaces[0], dual_space=A.dual_to_range_spaces[0], fun=tangential_trace),
        bempp.api.GridFunction(space=A.range_spaces[1], dual_space=A.dual_to_range_spaces[1], fun=neumann_trace)]

    bempp.api.enable_console_logging()
    sol = bempp.api.linalg.lu(A, rhs)

    #
    #   Compute scattered field
    #

    # Generate the evaluation points with numpy
    x, y, z = np.mgrid[x_a:x_b:nx * 1j, y_a:y_b:ny * 1j, 0:0:1j]
    points = np.vstack((x.ravel(), y.ravel(), z.ravel()))

    # Compute interior and exterior indices
    all_indices = np.ones(points.shape[1], dtype='uint32')

    # Find interior points
    mesh = pv.read(meshfile)

    points_poly = pv.PolyData(np.transpose(points))
    select = points_poly.select_enclosed_points(mesh)
    exterior_indices = np.array([ v==0 for v in select['SelectedPoints'] ])
    interior_indices = ~exterior_indices

    ext_points = points[:, exterior_indices]
    int_points = points[:, interior_indices]


    mpot0_int = bempp.api.operators.potential.maxwell.magnetic_field(sol[0].space, int_points, k_int)
    epot0_int = bempp.api.operators.potential.maxwell.electric_field(sol[1].space, int_points, k_int)
    mpot0_ext = bempp.api.operators.potential.maxwell.magnetic_field(sol[0].space, ext_points, k_ext)
    epot0_ext = bempp.api.operators.potential.maxwell.electric_field(sol[1].space, ext_points, k_ext)


    exterior_values = -epot0_ext * sol[1] - mpot0_ext * sol[0]
    interior_values = (np.sqrt(mu_r) / np.sqrt(eps_r) * epot0_int * sol[1] + mpot0_int * sol[0])
    
    # First compute the scattered field
    scattered_field = np.empty((3, points.shape[1]), dtype='complex128')
    scattered_field[:, :] = np.nan
    scattered_field[:, exterior_indices] = exterior_values

    # Now compute the total field
    total_field = np.empty((3, points.shape[1]), dtype='complex128')

    for ext_ind in np.arange(points.shape[1])[exterior_indices]:
        total_field[:, ext_ind] = scattered_field[:, ext_ind] + plane_wave(k_ext, polarization, direction, points[:, ext_ind])

    total_field[:, interior_indices] = interior_values
        
    # Compute the squared field density
    squared_scattered_field = np.sum(np.abs(scattered_field)**2, axis=0)
    squared_total_field = np.sum(np.abs(total_field)**2, axis=0)

    return squared_total_field, squared_scattered_field

