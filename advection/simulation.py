import importlib
import numpy as np
import matplotlib.pyplot as plt

import advection.advective_fluxes as flx
import mesh.patch as patch
from simulation_null import NullSimulation, grid_setup, bc_setup
import particles.particles as particles
import util.plot_tools as plot_tools


class Simulation(NullSimulation):

    def initialize(self):
        """
        Initialize the grid and variables for advection and set the initial
        conditions for the chosen problem.
        """

        my_grid = grid_setup(self.rp, ng=4)

        # create the variables
        my_data = patch.CellCenterData2d(my_grid)
        bc = bc_setup(self.rp)[0]
        my_data.register_var("density", bc)
        my_data.create()

        self.cc_data = my_data

        if self.rp.get_param("particles.do_particles") == 1:
            self.particles = particles.Particles(self.cc_data, bc, self.rp)

        # now set the initial conditions for the problem
        problem = importlib.import_module("advection.problems.{}".format(self.problem_name))
        problem.init_data(self.cc_data, self.rp)

    def method_compute_timestep(self):
        """
        Compute the advective timestep (CFL) constraint.  We use the
        driver.cfl parameter to control what fraction of the CFL
        step we actually take.
        """

        cfl = self.rp.get_param("driver.cfl")

        u = self.rp.get_param("advection.u")
        v = self.rp.get_param("advection.v")

        # the timestep is min(dx/|u|, dy/|v|)
        xtmp = self.cc_data.grid.dx/max(abs(u), self.SMALL)
        ytmp = self.cc_data.grid.dy/max(abs(v), self.SMALL)

        self.dt = cfl*min(xtmp, ytmp)

    def evolve(self):
        """
        Evolve the linear advection equation through one timestep.  We only
        consider the "density" variable in the CellCenterData2d object that
        is part of the Simulation.
        """

        dtdx = self.dt/self.cc_data.grid.dx
        dtdy = self.dt/self.cc_data.grid.dy

        flux_x, flux_y = flx.unsplit_fluxes(self.cc_data, self.rp, self.dt, "density")

        """
        do the differencing for the fluxes now.  Here, we use slices so we
        avoid slow loops in python.  This is equivalent to:

        myPatch.data[i,j] = myPatch.data[i,j] + \
                               dtdx*(flux_x[i,j] - flux_x[i+1,j]) + \
                               dtdy*(flux_y[i,j] - flux_y[i,j+1])
        """

        dens = self.cc_data.get_var("density")

        dens.v()[:, :] = dens.v() + dtdx*(flux_x.v() - flux_x.ip(1)) + \
                                    dtdy*(flux_y.v() - flux_y.jp(1))

        if self.particles is not None:
            myg = self.cc_data.grid
            u = self.rp.get_param("advection.u")
            v = self.rp.get_param("advection.v")

            u2d = myg.scratch_array() + u
            v2d = myg.scratch_array() + v

            self.particles.update_particles(u2d, v2d, self.dt,
                self.rp.get_param("advection.limiter"))

        # increment the time
        self.cc_data.t += self.dt
        self.n += 1

    def dovis(self):
        """
        Do runtime visualization.
        """
        plt.clf()

        dens = self.cc_data.get_var("density")

        myg = self.cc_data.grid

        _, axes, cbar_title = plot_tools.setup_axes(myg, 1)

        # plot density
        ax = axes[0]
        img = ax.imshow(np.transpose(dens.v()),
                   interpolation="nearest", origin="lower",
                   extent=[myg.xmin, myg.xmax, myg.ymin, myg.ymax],
                   cmap=self.cm)

        ax.set_xlabel("x")
        ax.set_ylabel("y")

        # needed for PDF rendering
        cb = axes.cbar_axes[0].colorbar(img)
        cb.solids.set_rasterized(True)
        cb.solids.set_edgecolor("face")

        plt.title("density")

        if self.particles is not None:
            particle_positions = self.particles.get_positions()

            # plot particles
            ax.scatter(particle_positions[:, 0], particle_positions[:, 1])
            ax.set_xlim([myg.xmin, myg.xmax])
            ax.set_ylim([myg.ymin, myg.ymax])

        plt.figtext(0.05, 0.0125, "t = {:10.5f}".format(self.cc_data.t))

        plt.pause(0.001)
        plt.draw()
