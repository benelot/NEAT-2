import numpy as np
import matplotlib.pyplot as pl

import pytest
import random
import copy

from neat import MorphLoc
from neat import PhysTree, GreensTree
from neat import CompartmentFitter
from neat.channels import channelcollection
import neat.tools.fittools.compartmentfitter as compartmentfitter


class TestCompartmentFitter():
    def loadTTree(self):
        '''
        Load the T-tree model

          6--5--4--7--8
                |
                |
                1
        '''
        print('>>> loading T-tree <<<')
        fname = 'test_morphologies/Tsovtree.swc'
        self.tree = PhysTree(fname, types=[1,3,4])
        self.tree.setPhysiology(0.8, 100./1e6)
        self.tree.fitLeakCurrent(-75., 10.)
        self.tree.setCompTree()

    def loadBallAndStick(self):
        '''
        Load the ball and stick model

        1--4
        '''
        self.tree = PhysTree(file_n='test_morphologies/ball_and_stick.swc')
        self.tree.setPhysiology(0.8, 100./1e6)
        self.tree.setLeakCurrent(100., -75.)
        self.tree.setCompTree()

    def loadBall(self):
        '''
        Load point neuron model
        '''
        self.tree = PhysTree(file_n='test_morphologies/ball.swc')
        # capacitance and axial resistance
        self.tree.setPhysiology(0.8, 100./1e6)
        # ion channels
        k_chan = channelcollection.Kv3_1()
        self.tree.addCurrent(k_chan, 0.766*1e6, -85.)
        na_chan = channelcollection.Na_Ta()
        self.tree.addCurrent(na_chan, 1.71*1e6, 50.)
        # fit leak current
        self.tree.fitLeakCurrent(-75., 10.)
        # set computational tree
        self.tree.setCompTree()

    def testTreeStructure(self):
        self.loadTTree()
        cm = CompartmentFitter(self.tree)
        # set of locations
        fit_locs1 = [(1,.5), (4,.5), (5,.5)] # no bifurcations
        fit_locs2 = [(1,.5), (4,.5), (5,.5), (8,.5)] # w bifurcation, should be added
        fit_locs3 = [(1,.5), (4,1.), (5,.5), (8,.5)] # w bifurcation, already added

        # test fit_locs1, no bifurcation are added
        # input paradigm 1
        cm.setCTree(fit_locs1, extend_w_bifurc=True)
        fl1_a = cm.tree.getLocs('fit locs')
        cm.setCTree(fit_locs1, extend_w_bifurc=False)
        fl1_b = cm.tree.getLocs('fit locs')
        assert len(fl1_a) == len(fl1_b)
        for fla, flb in zip(fl1_a, fl1_b): assert fla == flb
        # input paradigm 2
        cm.tree.storeLocs(fit_locs1, 'fl1')
        cm.setCTree('fl1', extend_w_bifurc=True)
        fl1_a = cm.tree.getLocs('fit locs')
        assert len(fl1_a) == len(fl1_b)
        for fla, flb in zip(fl1_a, fl1_b): assert fla == flb
        # test tree structure
        assert len(cm.ctree) == 3
        for cn in cm.ctree: assert len(cn.child_nodes) <= 1

        # test fit_locs2, a bifurcation should be added
        with pytest.warns(UserWarning):
            cm.setCTree(fit_locs2, extend_w_bifurc=False)
        fl2_b = cm.tree.getLocs('fit locs')
        cm.setCTree(fit_locs2, extend_w_bifurc=True)
        fl2_a = cm.tree.getLocs('fit locs')
        assert len(fl2_a) == len(fl2_b) + 1
        for fla, flb in zip(fl2_a, fl2_b): assert fla == flb
        assert fl2_a[-1] == (4,1.)
        # test tree structure
        assert len(cm.ctree) == 5
        for cn in cm.ctree:
            assert len(cn.child_nodes) <= 1 if cn.loc_ind != 4 else \
                   len(cn.child_nodes) == 2

        # test fit_locs2, no bifurcation should be added as it is already present
        cm.setCTree(fit_locs3, extend_w_bifurc=True)
        fl3 = cm.tree.getLocs('fit locs')
        for fl_, fl3 in zip(fit_locs3, fl3): assert fl_ == fl3
        # test tree structure
        assert len(cm.ctree) == 4
        for cn in cm.ctree:
            assert len(cn.child_nodes) <= 1 if cn.loc_ind != 1 else \
                   len(cn.child_nodes) == 2

    def _checkChannels(self, tree, channel_names):
        assert isinstance(tree, compartmentfitter.FitTreeGF)
        assert set(tree.channel_storage.keys()) == set(channel_names)
        for node in tree:
            assert set(node.currents.keys()) == set(channel_names + ['L'])

    def testCreateTreeGF(self):
        self.loadBall()
        cm = CompartmentFitter(self.tree)

        # create tree with only 'L'
        tree_pas = cm.createTreeGF()
        self._checkChannels(tree_pas, [])
        # create tree with only 'Na_Ta'
        tree_na = cm.createTreeGF(['Na_Ta'])
        self._checkChannels(tree_na, ['Na_Ta'])
        # create tree with only 'Kv3_1'
        tree_k = cm.createTreeGF(['Kv3_1'])
        self._checkChannels(tree_k, ['Kv3_1'])
        # create tree with all channels
        tree_all = cm.createTreeGF(['Na_Ta', 'Kv3_1'])
        self._checkChannels(tree_all, ['Na_Ta', 'Kv3_1'])

    def reduceExplicit(self):
        self.loadBall()

        freqs = np.array([0.])
        locs = [(1, 0.5)]
        e_eqs = [-75., -55., -35., -15.]
        # create compartment tree
        ctree = self.tree.createCompartmentTree(locs)
        ctree.addCurrent(channelcollection.Na_Ta(), 50.)
        ctree.addCurrent(channelcollection.Kv3_1(), -85.)

        # create tree with only leak
        greens_tree_pas = self.tree.__copy__(new_tree=GreensTree())
        greens_tree_pas[1].currents = {'L': greens_tree_pas[1].currents['L']}
        greens_tree_pas.setCompTree()
        greens_tree_pas.setImpedance(freqs)
        # compute the passive impedance matrix
        z_mat_pas = greens_tree_pas.calcImpedanceMatrix(locs)[0]

        # create tree with only potassium
        greens_tree_k = self.tree.__copy__(new_tree=GreensTree())
        greens_tree_k[1].currents = {key: val for key, val in greens_tree_k[1].currents.items() \
                                               if key != 'Na_Ta'}
        # compute potassium impedance matrices
        z_mats_k = []
        for e_eq in e_eqs:
            greens_tree_k.setEEq(e_eq)
            greens_tree_k.setCompTree()
            greens_tree_k.setImpedance(freqs)
            z_mats_k.append(greens_tree_k.calcImpedanceMatrix(locs))

        # create tree with only sodium
        greens_tree_na = self.tree.__copy__(new_tree=GreensTree())
        greens_tree_na[1].currents = {key: val for key, val in greens_tree_na[1].currents.items() \
                                               if key != 'Kv3_1'}
        # create state variable expansion points
        svs = []; e_eqs_ = []
        na_chan = greens_tree_na.channel_storage['Na_Ta']
        for e_eq1 in e_eqs:
            sv1 = na_chan.computeVarInf(e_eq1)
            for e_eq2 in e_eqs:
                e_eqs_.append(e_eq1)
                sv2 = na_chan.computeVarInf(e_eq2)
                svs.append(np.array([[sv1[0,0], sv2[0,1]]]))

        # compute sodium impedance matrices
        z_mats_na = []
        for sv, eh in zip(svs, e_eqs_):
            greens_tree_na.setEEq(eh)
            greens_tree_na[1].setExpansionPoint('Na_Ta', sv)
            greens_tree_na.setCompTree()
            greens_tree_na.setImpedance(freqs)
            z_mats_na.append(greens_tree_na.calcImpedanceMatrix(locs))

        # passive fit
        ctree.computeGMC(z_mat_pas)

        # potassium channel fit matrices
        fit_mats_k = []
        for z_mat_k, e_eq in zip(z_mats_k, e_eqs):
            mf, vt = ctree.computeGSingleChanFromImpedance(
                            'Kv3_1', z_mat_k, e_eq, freqs,
                            other_channel_names=['L'], action='return'
                            )
            fit_mats_k.append([mf, vt])

        # sodium channel fit matrices
        fit_mats_na = []
        for z_mat_na, e_eq, sv in zip(z_mats_na, e_eqs_, svs):
            mf, vt = ctree.computeGSingleChanFromImpedance(
                            'Na_Ta', z_mat_na, e_eq, freqs,
                            sv=sv, other_channel_names=['L'], action='return'
                            )
            fit_mats_na.append([mf, vt])

        return fit_mats_na, fit_mats_k

    def testChannelFitMats(self):
        self.loadBall()
        cm = CompartmentFitter(self.tree)
        cm.setCTree([(1,.5)])
        # check if reversals are correct
        for key in set(cm.ctree[0].currents) - {'L'}:
            assert np.abs(cm.ctree[0].currents[key][1] - \
                          self.tree[1].currents[key][1]) < 1e-10

        # fit the passive model
        cm.fitPassive(use_all_channels=False)

        fit_mats_cm_na = cm.evalChannel('Na_Ta', parallel=False)
        fit_mats_cm_k = cm.evalChannel('Kv3_1', parallel=False)
        fit_mats_control_na, fit_mats_control_k = self.reduceExplicit()
        # test whether potassium fit matrices agree
        for fm_cm, fm_control in zip(fit_mats_cm_k, fit_mats_control_k):
            assert np.allclose(np.sum(fm_cm[0]), fm_control[0][0,0]) # feature matrices
            assert np.allclose(fm_cm[1], fm_control[1]) # target vectors
        # test whether sodium fit matrices agree
        for fm_cm, fm_control in zip(fit_mats_cm_na[4:], fit_mats_control_na):
            assert np.allclose(np.sum(fm_cm[0]), fm_control[0][0,0]) # feature matrices
            assert np.allclose(fm_cm[1], fm_control[1]) # target vectors





if __name__ == '__main__':
    tcf = TestCompartmentFitter()
    # tcf.testTreeStructure()
    # tcf.testCreateTreeGF()
    tcf.testChannelFitMats()
