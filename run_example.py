import build123d as cad
import ocp_vscode as ocp
import numpy as np

def hyperbolic_surface(r,b,a):
    z = b/a * np.sqrt(a**2 - r**2)
    return z

def revolve_curve(r,z):
    sPnts = [ (r[i], z[i]) for i in range(len(z))]
    l1 = cad.Spline(*sPnts)
    l2 = cad.Line(l1 @ 1, (0,z[-1]))
    l3 = cad.Line((0,z[-1]), l1 @ 0)
    surf = cad.make_face([l1, l2, l3])
    solid = cad.revolve(surf, cad.Axis.Y)
    return solid

n_spline = 20
b = 5
a = 12.5

r = np.linspace(0,a,n_spline)
z = np.array([hyperbolic_surface(rr,b,a) for rr in r])

solid = revolve_curve(r,z)
ocp.show(solid)
cad.export_step(solid,"hyperbolic_lens.step")

#
#   Use GMSH for meshing
#

import gmsh
gmsh.initialize()
gmsh.option.setNumber("General.Terminal", 3)
gmsh.model.add("lens_model")

gmsh.merge("hyperbolic_lens.step")
gmsh.option.setNumber('Mesh.MeshSizeMax', 1)

gmsh.model.mesh.generate(2)
gmsh.model.geo.synchronize()
gmsh.write("hyperbolic_lens.stl")


#
#   View mesh with Pyvista
#

import pyvista as pv
mesh = pv.read("hyperbolic_lens.stl")
p = pv.Plotter()
p.add_mesh(mesh, show_edges=True)
p.show()


#
#   Call Bempp solver
#

import bempp_solver


meshfile = "hyperbolic_lens.stl"
frequency = 60E6    # (in Hz, but geometry is in mm)
eps_r = 2.1
mu_r = 1.0
theta = np.pi / 2   # Incident wave angle (radians)

# For near field computation
nx = 200
ny = 200
x_a, x_b = -40, 40
y_a, y_b = -40, 60

squared_total_field, squared_scattered_field = bempp_solver.solve(meshfile, frequency, eps_r, mu_r, theta, nx, ny, x_a, x_b, y_a, y_b)

#
#   Plotting
#

from matplotlib import pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
from matplotlib.patches import Circle
plt.rcParams['figure.figsize'] = (20, 16) 

# Show the resulting images
scattered_image = squared_scattered_field.reshape(nx, ny).T
total_image = squared_total_field.reshape(nx, ny).T
fig, axes = plt.subplots(1, 2, sharex=True, sharey=True)

f0 = axes[0].imshow(scattered_image, origin='lower', cmap='magma',
                    extent=[x_a, x_b, y_a, y_b], vmin=0, vmax=5)


axes[0].set_title("Squared scattered field strength")
divider = make_axes_locatable(axes[0])
cax = divider.append_axes("right", size="5%", pad=0.05)
fig.colorbar(f0, cax=cax)

f1 = axes[1].imshow(total_image, origin='lower', cmap='magma',
                    extent=[x_a, x_b, y_a, y_b], vmin=0, vmax=5)

axes[1].set_title("Squared total field strength")
divider = make_axes_locatable(axes[1])
cax = divider.append_axes("right", size="5%", pad=0.05)
fig.colorbar(f1, cax=cax)

plt.show()
