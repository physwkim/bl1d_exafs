import inspect
import bluesky.plans as bp
import os
import numpy as np


class EnergyScanList():
    """ make an E-Scan array """
    def __init__(self, SRB=None, eMode=None, StepSize=None,\
                 SRBOnOff=None, Time=None):

        self.SRB = SRB
        self.eMode = eMode
        self.StepSize = StepSize
        self.SRBOnOff = SRBOnOff
        self.Time = Time
        self.energy_list = []
        self.makeArray()

    def makeArray(self):
        """ make an energy scan list """
        for idx in range(len(self.SRB)-1):
            active = self.SRBOnOff[idx]
            eMode = self.eMode[idx]
            eMode_next = self.eMode[idx+1]

            if active:
                if eMode and eMode_next:
                    for item in np.arange(self.SRB[idx],
                                          self.SRB[idx+1],
                                          self.StepSize[idx]):
                        self.energy_list.append(round(item,5))

                elif not eMode and eMode_next:
                    for item in np.arange(self.energy_list[-1],
                                          self.SRB[idx+1],
                                          self.StepSize[idx]):
                        self.energy_list.append(round(item,5))

                else:
                    if not len(self.energy_list):
                        raise ValueError

                    for item in self.kMode(self.energy_list[-1],
                                           self.SRB[idx+1],
                                           self.StepSize[idx]):
                        self.energy_list.append(round(item,5))


    def kMode(self, start_energy_eV, stop_energy_k, step_energy_k):
        """ kMode energy list """
        k_energy_list = []
        a = np.sqrt(start_energy_eV) * 0.512
        stop_energy_eV = (stop_energy_k/0.512)**2
        N = 1

        while True:
            energy_eV = (((step_energy_k * N)+a)/0.512)**2

            if (energy_eV >= stop_energy_eV):
                break

            k_energy_list.append(energy_eV)
            N += 1

        return k_energy_list
