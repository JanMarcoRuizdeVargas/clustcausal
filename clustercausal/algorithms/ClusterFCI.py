from __future__ import annotations

import warnings
from queue import Queue
from typing import List, Set, Tuple, Dict
from numpy import ndarray

from causallearn.graph.Edge import Edge
from causallearn.graph.Endpoint import Endpoint
from causallearn.graph.Graph import Graph
from causallearn.graph.GraphNode import GraphNode
from causallearn.graph.Node import Node
from causallearn.utils.ChoiceGenerator import ChoiceGenerator
from causallearn.utils.DepthChoiceGenerator import DepthChoiceGenerator
from causallearn.utils.cit import *
from causallearn.utils.Fas import fas
from causallearn.utils.PCUtils.BackgroundKnowledge import BackgroundKnowledge
from causallearn.search.ConstraintBased.FCI import *

from clustercausal.clusterdag.ClusterDAG import ClusterDAG


class ClusterFCI:
    def __init__(
        self,
        cdag: ClusterDAG,
        data: ndarray,
        alpha: float,
        indep_test: str = "fisherz",
        stable: bool = True,
        uc_rule: int = 0,
        uc_priority: int = 2,
        background_knowledge: BackgroundKnowledge | None = None,
        verbose: bool = False,
        show_progress: bool = True,
        **kwargs,
    ) -> None:
        """
        Set parameters for the clust PC algorithm.
        """
        self.cdag = cdag
        self.data = data
        self.node_names = cdag.node_names
        self.alpha = alpha

        self.stable = stable
        self.uc_rule = uc_rule
        self.uc_priority = uc_priority
        self.background_knowledge = background_knowledge
        self.verbose = verbose
        self.show_progress = show_progress
        self.kwargs = kwargs
        self.cdag.cdag_to_mpdag()  # Get pruned MPDAG from CDAG
        self.cdag.get_cluster_topological_ordering()  # Get topological ordering of CDAG

        # Set independence test
        self.cdag.cg.test = CIT(self.data, indep_test, **kwargs)

    def run(self):
        """
        Runs the C-FCI algorithm.
        """
        start = time.time()
        no_of_var = self.data.shape[1]
        # pbar = tqdm(total=no_of_var) if self.show_progress else None
        for cluster_name in self.cdag.cdag_list_of_topological_sort:
            print(f"\nBeginning work on cluster {cluster_name}")
            cluster = self.cdag.get_node_by_name(
                cluster_name, cg=self.cdag.cluster_graph
            )
            for parent in self.cdag.cluster_graph.G.get_parents(cluster):
                print(
                    "\nInter phase between low cluster"
                    f" {cluster.get_name()} and parent {parent.get_name()}"
                )
                self.inter_cluster_phase(cluster, parent)
            # TODO Apply Meek edge orientation rules here too?
            print(f"\nIntra phase in cluster {cluster.get_name()}")
            self.intra_cluster_phase(cluster)

        def inter_cluster_phase(
            cluster,
            parent,
            cdag=self.cdag,
            dataset: ndarray = self.data,
            independence_test_method: str = fisherz,
            alpha: float = 0.05,
            depth: int = -1,
            max_path_length: int = -1,
            verbose: bool = False,
            background_knowledge: BackgroundKnowledge | None = None,
            **kwargs,
        ):
            """
            Runs the inter cluster phase of the C-FCI algorithm.
            TODO
            """

            # Restrict to local graph
            cdag = cdag
            dataset = self.data
            node_to_global_indice = cdag.cg.G.node_map  # Dict: Node -> int
            local_graph = cdag.get_local_graph(cluster)
            # map global_indices to local_indices
            global_graph = cdag.cg
            global_indices_to_local_indices = (
                ClusterDAG.make_mapping_global_to_local_indices(
                    global_graph, local_graph
                )
            )
            local_indices_to_global_indices = (
                ClusterDAG.make_mapping_local_to_global_indices(
                    global_graph, local_graph
                )
            )
            # global_indice_to_local_indice = {}
            # for node in self.cdag.cg.G.nodes:
            #     global_indice = self.cdag.cg.G.node_map[node]
            #     local_indice = local_graph.G.node_map[node]
            #     global_indice_to_local_indice[global_indice] = local_indice
            # local_indice_to_global_indice = {}
            # for global_indice in list(global_indice_to_local_indice.keys()):
            #     local_indice = global_indice_to_local_indice[global_indice]
            #     local_indice_to_global_indice[local_indice] = global_indice

            # restrict data array via local graph
            local_data = dataset[
                :, list(local_indices_to_global_indices.keys())
            ]
            local_graph.G, sep_sets = fas(
                data=local_data,
                nodes=local_graph.G.nodes,
                independence_test_method=self.cdag.cg.test,
                alpha=self.alpha,
                knowledge=self.background_knowledge,
                depth=-1,
                verbose=self.verbose,
                stable=self.stable,
                show_progress=self.show_progress,
            )

            # for node in local_graph.

            # run FCI in local graph

            # map edge changes back to global graph

            # map sepset changes back to global graph

        def intra_cluster_phase(cluster):
            pass
            # Restrict to local graph

            # map global_indices to local_indices
            global_indices_to_local_indices = {}

            # run FCI in local graph

            # map edge changes back to global graph

            # map sepset changes back to global graph

        @staticmethod
        def get_global_indice_from_local_indice(local_indice):
            pass
