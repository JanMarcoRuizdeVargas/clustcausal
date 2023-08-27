import numpy as np
import pandas as pd
import networkx as nx
import causallearn

# import castle
import pydot
import logging

from itertools import combinations
from typing import List
from causallearn.graph.GraphClass import CausalGraph
from causallearn.utils.PCUtils.BackgroundKnowledge import BackgroundKnowledge
from causallearn.graph.GraphNode import GraphNode
from causallearn.graph.Node import Node
from causallearn.graph.GeneralGraph import GeneralGraph

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class ClusterDAG:
    """
    Class for functionality regarding CDAGS

    attributes:
        clusters: dictionary of clusters
        cluster_edges: list of tuples of cluster edges
        graph: CausalGraph object
        background_knowledge: BackgroundKnowledge object
        node_names: list of node names
        node_indices: dictionary that points to which cluster the node is in

    methods:
        cdag_to_mpdag: constructs a MPDAG from a CDAG

    """

    def __init__(
        self,
        cluster_mapping: dict,
        cluster_edges: list,
        node_names: list | None = None,
    ):
        """
        Construct a CDAG object from a cluster dictionary
        The CDAG is stored as a dictionary.
        The cluster_nodes are stored as a dictionary pointing
        to a list of cluster members.
        The cluster_edges are stored as a list of tuples.
        An example CDAG:
            cdag.cluster_mapping= {'C1':['X1','X2','X3'], 'C2': ['X4','X5']}
            cdag.cluster_edges = [('C1','C2')]
            cdag.cg = CausalGraphObject
            cdag.cluster_graph = CausalGraphObject of clusters
        """
        self.data = None
        self.true_dag = None
        self.cluster_mapping = cluster_mapping
        self.cluster_edges = cluster_edges
        self.node_names = node_names  # must be in same order as in data
        if self.node_names is None:  # This can mess up order of nodes!
            self.node_names = []
            for cluster in self.cluster_mapping:
                self.node_names.extend(self.cluster_mapping[cluster])

        self.node_indices = (
            {}
        )  # Dictionary that points to which cluster the node is in
        for node in self.node_names:
            for cluster, vertice in self.cluster_mapping.items():
                if node in vertice:
                    self.node_indices[node] = cluster
        self.cluster_graph = CausalGraph(
            no_of_var=len(self.cluster_mapping),
            node_names=list(self.cluster_mapping.keys()),
        )
        for edge in self.cluster_graph.G.get_graph_edges():
            cluster1 = edge.get_node1()
            cluster2 = edge.get_node2()
            cluster1_name = cluster1.get_name()
            cluster2_name = cluster2.get_name()
            if cluster1 != cluster2:
                if (cluster1_name, cluster2_name) not in self.cluster_edges:
                    self.cluster_graph.G.remove_edge(edge)
                    # logging.info(
                    #     "removed edge:"
                    #     f" ({cluster1.get_name()},{cluster2.get_name()})"
                    # )
                if (cluster1_name, cluster2_name) in self.cluster_edges:
                    self.cluster_graph.G.remove_edge(edge)
                    self.cluster_graph.G.add_directed_edge(cluster1, cluster2)
                    # logging.info(
                    #     "oriented edge:"
                    #     f" ({cluster1.get_name()},{cluster2.get_name()})"
                    # )

    def cdag_to_pag(self, forbidden_latent_edges: list):
        """
        If a C-DAG with latent variables is wanted, this function
        adds the latent edges to the cluster graph.
        TODO
        """
        for edge in forbidden_latent_edges:
            self.cluster_graph.G.add_directed_edge(edge[0], edge[1])

    def cdag_to_mpdag(self) -> CausalGraph:
        """
        Constructs a MPDAG (maximally partially directed DAG)
        from a CDAG and stores it in a causallearn CausalGraph.
        """
        # Create the list of node_names needed for CausalGraph
        self.cg = CausalGraph(
            no_of_var=len(self.node_names), node_names=self.node_names
        )

        # Remove edges that are forbidden by the CDAG
        for edge in self.cg.G.get_graph_edges():
            # Get clusters of the nodes from the edge
            node1_name = edge.get_node1().get_name()
            node2_name = edge.get_node2().get_name()
            dictionary = self.cluster_mapping
            c1_name = self.find_key(dictionary=dictionary, value=node1_name)
            c2_name = self.find_key(dictionary=dictionary, value=node2_name)
            # If the nodes are in different clusters, check if the edge is forbidden
            if c1_name != c2_name:
                if (c1_name, c2_name) not in self.cluster_edges and (
                    c2_name,
                    c1_name,
                ) not in self.cluster_edges:
                    self.cg.G.remove_edge(edge)
                if (c1_name, c2_name) in self.cluster_edges:
                    self.cg.G.remove_edge(edge)
                    self.cg.G.add_directed_edge(
                        edge.get_node1(), edge.get_node2()
                    )
                if (c2_name, c1_name) in self.cluster_edges:
                    self.cg.G.remove_edge(edge)
                    self.cg.G.add_directed_edge(
                        edge.get_node2(), edge.get_node1()
                    )
                # TODO: Latent variables

        # OLD CODE
        """
        # Remove edges that are forbidden by the CDAG
        # self.background_knowledge = BackgroundKnowledge()
        for edge in self.cg.G.get_graph_edges():
            # There must be a better way to do this by only adressing the edges needed to be changed
            node1 = edge.get_node1()
            node2 = edge.get_node2()
            cluster1 = self.node_indices[node1.get_name()]
            cluster2 = self.node_indices[node2.get_name()]
            if cluster1 != cluster2:
                if (cluster1, cluster2) not in self.cluster_edges:
                    self.cg.G.remove_edge(edge)
                    logging.info(
                        "removed edge:"
                        f" ({node1.get_name()},{node2.get_name()})"
                    )
                if (cluster1, cluster2) in self.cluster_edges:
                    self.cg.G.remove_edge(edge)
                    self.cg.G.add_directed_edge(node1, node2)
                    logging.info(
                        "oriented edge:"
                        f" ({node1.get_name()},{node2.get_name()})"
                    )
                    """
        # return self.cg

    def draw_mpdag(self):
        """
        Draws the mpdag using causallearn visualization
        """
        self.cg.draw_pydot_graph()

    def draw_cluster_graph(self):
        """
        Draws the cluster DAG using causallearn visualization
        """
        self.cluster_graph.draw_pydot_graph()

    def get_cluster_topological_ordering(self) -> list:
        """
        Calculates a topological ordering of the CDAG
        and saves it to self.cdag_topological_sort and
        self.cdag_list_of_topological_sort
        Returns:
        list of node names
        """
        nx_helper_graph = nx.DiGraph()
        nx_helper_graph.add_edges_from(self.cluster_edges)
        nx_helper_graph.add_nodes_from(list(self.cluster_mapping.keys()))
        topological_generator = nx.topological_sort(nx_helper_graph)
        self.cdag_list_of_topological_sort = list(topological_generator)
        # if len(self.cdag_list_of_topological_sort) == 0:
        #     # If only one cluster, nx doesn't return a list containing only the cluster
        #     self.cdag_list_of_topological_sort = list(
        #         self.cluster_mapping.keys()
        #     )
        #     return list(self.cluster_mapping.keys())
        return self.cdag_list_of_topological_sort

    def get_parents_plus(self, cluster: Node) -> tuple:
        """
        Gets the pa+ set of a cluster, i.e. the cluster union the parents
        Parameters:
        cluster (Node object in the CausalGraph instance cdag.cluster_graph
        Returns:
        Tuple of two lists: (relevant_clusters, relevant_nodes)
        relevant_clusters is list of Node objects in cdag.cluster_graph
        relevant_nodes is list of Node objects in cdag.cg
        """
        relevant_clusters = [cluster]
        relevant_clusters.extend(self.cluster_graph.G.get_parents(cluster))
        cluster_name = cluster.get_name()
        names_of_relevant_nodes = []
        for clust in relevant_clusters:
            names_of_relevant_nodes.extend(
                self.cluster_mapping[clust.get_name()]
            )
        relevant_nodes = []
        for node_name in names_of_relevant_nodes:
            relevant_nodes.append(self.get_node_by_name(node_name, self.cg))
        return relevant_clusters, relevant_nodes

    def max_degree_of_cluster_parents(self, cluster: Node) -> int:
        # First element is cluster itself, remove it
        # cluster_parents is Node instance
        cluster_parents, _ = self.get_parents_plus(cluster)
        cluster_parents.pop(0)
        cluster_parents_max_degree = 0
        for clust_parent in cluster_parents:
            deg = self.max_degree_of_cluster(clust_parent)
            if deg > cluster_parents_max_degree:
                cluster_parents_max_degree = deg
        return cluster_parents_max_degree

    def max_degree_of_cluster_parents_in_local_graph(
        self, cluster: Node, local_graph
    ) -> int:
        # First element is cluster itself, remove it
        # cluster_parents is Node instance
        cluster_parents, _ = self.get_parents_plus(cluster)
        cluster_parents.pop(0)
        max_degree = 0
        for clust_parent in cluster_parents:
            for node in local_graph.G.nodes:
                if (
                    node.get_name()
                    in self.cluster_mapping[clust_parent.get_name()]
                ):
                    deg = local_graph.G.get_degree(node)
                    if deg > max_degree:
                        max_degree = deg
        return max_degree

    def get_local_graph(self, cluster: Node) -> CausalGraph:
        """
        Define the local graph on which to run the intra cluster phase, restrict data
        to cluster union parents of cluster
        Parameters:
        cluster (Node object in the CausalGraph instance cdag.cluster_graph
        Returns:
        A CausalGraph object, where CausalGraph.G is replaced with a subgraph
        (GeneralGraph) object, restricted to the relevant nodes (cluster union parents)
        """
        _, relevant_nodes = self.get_parents_plus(cluster)
        relevant_node_names = []
        for node in relevant_nodes:
            relevant_node_names.append(node.get_name())

        local_graph = CausalGraph(
            no_of_var=len(relevant_nodes), node_names=relevant_node_names
        )

        # local_graph = CausalGraph(no_of_var = len(relevant_nodes),
        #                                               node_names = relevant_node_names)
        local_graph.G = self.subgraph(relevant_nodes)
        return local_graph

    def get_nonchilds(self, node_index: int) -> list:
        """
        Returns the indices of the nonchilds of a node
        """
        Neigh_x = self.cg.neighbors(node_index)
        node_x = ClusterDAG.get_key_by_value(self.cg.G.node_map, node_index)
        Child_x_nodes = self.cg.G.get_children(node_x)
        Child_x_indices = [self.cg.G.node_map[node] for node in Child_x_nodes]
        Nonchilds_x = np.setdiff1d(Neigh_x, Child_x_indices)
        return Nonchilds_x

    def subgraph(self, nodes: List[Node]) -> GeneralGraph:
        """
        Returns a subgraph, where the nodes are the ones in the list nodes
        Adapted from causallearn.graph.GeneralGraph.subgraph, but theirs was bugged
        Parameters:
        nodes (list of Node objects)
        Returns:
        A GeneralGraph with GeneralGraph.graph a
        ndarray of shape (len(nodes), len(nodes)), the adjacency matrix of the subgraph
        """
        # Put nodes into self.cg.G.node_map order
        nodes = sorted(nodes, key=lambda node: self.cg.G.node_map[node])

        subgraph = GeneralGraph(nodes)

        graph = self.cg.G.graph

        nodes_to_delete = []

        for i in range(self.cg.G.num_vars):
            if not (self.cg.G.nodes[i] in nodes):
                nodes_to_delete.append(i)

        graph = np.delete(graph, nodes_to_delete, axis=0)
        graph = np.delete(graph, nodes_to_delete, axis=1)

        subgraph.graph = graph
        subgraph.reconstitute_dpath(subgraph.get_graph_edges())

        return subgraph

    @staticmethod
    def make_mapping_local_to_global_indices(
        global_graph: CausalGraph, local_graph: CausalGraph
    ) -> dict:
        """
        Makes a mapping from local indices to global indices
        Parameters:
        global_graph (CausalGraph object)
        local_graph (CausalGraph object)
        Returns:
        Dictionary with keys local indices and values global indices
        """
        local_indice_to_global_indice = {}
        for node in local_graph.G.nodes:
            global_indice = global_graph.G.node_map[node]
            local_indice = local_graph.G.node_map[node]
            local_indice_to_global_indice[local_indice] = global_indice
        return local_indice_to_global_indice

    @staticmethod
    def make_mapping_global_to_local_indices(
        global_graph: CausalGraph, local_graph: CausalGraph
    ) -> dict:
        """
        Makes a mapping from global indices to local indices
        Parameters:
        global_graph (CausalGraph object)
        local_graph (CausalGraph object)
        Returns:
        Dictionary with keys global indices and values local indices
        """
        global_indice_to_local_indice = {}
        for node in global_graph.G.nodes:
            global_indice = global_graph.G.node_map[node]
            local_indice = local_graph.G.node_map[node]
            global_indice_to_local_indice[global_indice] = local_indice
        return global_indice_to_local_indice

    def max_degree_of_cluster(self, cluster: Node) -> int:
        """
        Calculates the max degree of nodes in the cluster
        within the self.cg CausalGraph
        """
        max_degree = 0
        nodes_in_cluster = self.cluster_mapping[cluster.get_name()]
        for node_name in nodes_in_cluster:
            node = self.get_node_by_name(node_name, self.cg)
            deg = self.cg.G.get_degree(node)
            if deg > max_degree:
                max_degree = deg
        return max_degree

    def max_nonchild_degree_of_cluster(self, cluster: Node) -> int:
        """
        Calculates the max nonchild degree of nodes in the cluster
        within the self.cg CausalGraph
        """
        max_degree = 0
        nodes_in_cluster = self.cluster_mapping[cluster.get_name()]
        for node_name in nodes_in_cluster:
            node = self.get_node_by_name(node_name, self.cg)
            deg = len(self.get_nonchilds(self.cg.G.node_map[node]))
            if deg > max_degree:
                max_degree = deg
        return max_degree

    def max_nonchilds_of_cluster_nodes(
        self, cluster: Node, graph_to_use: CausalGraph
    ) -> int:
        """
        Returns the maximum degree of the nodes in the cluster in the
        local graph, which includes parents of the cluster.
        Needed for stopping depth of PC algorithm.
        Parameters:
        cluster (Node object in the CausalGraph instance cdag.cluster_graph)
        graph_to_use (CausalGraph object)
        Returns:
        Integer, maximum amount of nonchilds of any node in the cluster
        --- in NewClusterPC will be replaced by max_degree_of_cluster
        --- and max_nonchild_degree_of_cluster
        """
        max_degree = 0
        nodes_in_cluster = self.cluster_mapping[cluster.get_name()]
        for node_name in nodes_in_cluster:
            node = self.get_node_by_name(node_name, graph_to_use)
            deg = graph_to_use.G.get_degree(node)
            if deg > max_degree:
                max_degree = deg
        return max_degree

    def get_node_indices_of_cluster(self, cluster):
        """
        Takes in a cluster and returns the node indices in the adjacency matrix
        self.cg.node_map
        """
        nodes_names_in_cluster = self.cluster_mapping[cluster.get_name()]
        nodes_in_cluster = self.get_list_of_nodes_by_name(
            list_of_node_names=nodes_names_in_cluster, cg=self.cg
        )
        subgraph_cluster = CausalGraph(
            len(nodes_names_in_cluster), nodes_names_in_cluster
        )
        subgraph_cluster.G = self.subgraph(nodes_in_cluster)
        cluster_node_indices = np.array(
            [self.cg.G.node_map[node] for node in subgraph_cluster.G.nodes]
        )
        return cluster_node_indices

    @staticmethod
    def get_node_by_name(node_name, cg: CausalGraph):
        """
        Helper function to get Node object from node_name regarding GraphNode object
        Parameters:
        node_name (string)
        cg (CausalGraph object) - the graph to look in
        Returns:
        Node object
        """
        for node in cg.G.nodes:
            if node.get_name() == node_name:
                return node

    @staticmethod
    def get_list_of_nodes_by_name(list_of_node_names, cg: CausalGraph):
        """
        Helper function to get list of Node objects from list of node_names
        regarding GraphNode object
        Parameters:
        list_of_node_names (list of strings)
        cg (CausalGraph object) - the graph to look in
        Returns:
        list of Node objects
        """
        list_of_nodes = []
        for node_name in list_of_node_names:
            list_of_nodes.append(ClusterDAG.get_node_by_name(node_name, cg))
        return list_of_nodes

    @staticmethod
    def get_node_names_from_list(list_of_nodes):
        """
        Helper function to get list of node names from list of Node objects
        """
        node_names = []
        for node in list_of_nodes:
            node_names.append(node.get_name())
        return node_names

    @staticmethod
    def get_key_by_value(dictionary: dict, value):
        # Helper function to get Node object from node_map value i regarding GraphNode object
        # Only works if key-value is a 1-1 correspondence
        for key, val in dictionary.items():
            if val == value:
                return key
        return None  # Value not found in the dictionary

    @staticmethod
    def find_key(dictionary: dict, value) -> list:
        # Helper function to get key if value is in
        # value list of dictionary
        # Dictionary must be of type dict{key: list}
        # value must be unique to one key
        keys = []
        for key, values in dictionary.items():
            if value in values:
                return key
        return None  # Value not found in the dictionary

    def cdag_from_background_knowledge(self):
        """
        Construct a CDAG object from background knowledge
        Types of background knowledge:
            Todo
            -required edges
            -forbidden edges
            -required ancestors
            -forbidden ancestors
        """
        pass

    def background_knowledge_from_cdag(self):
        """
        Construct background knowledge from a CDAG object
        Types of background knowledge:
            Todo
            -required edges
            -forbidden edges
            -required ancestors
            -forbidden ancestors
        """
        pass

    def get_cluster_connectedness(self):
        """
        Returns the cluster connectedness of the CDAG
        """
        if self.true_dag is None:
            raise ValueError("True DAG not set")
        intra_edge_ratio = []
        for c_name in self.cluster_mapping.keys():
            edge_count = 0
            no_of_nodes = len(self.cluster_mapping[c_name])
            for n1, n2 in combinations(self.cluster_mapping[c_name], 2):
                n1 = self.get_node_by_name(n1, self.true_dag)
                n2 = self.get_node_by_name(n2, self.true_dag)
                n1 = self.true_dag.G.node_map[n1]
                n2 = self.true_dag.G.node_map[n2]
                if n1 in self.true_dag.neighbors(n2):
                    edge_count += 1
            intra_edge_ratio.append(
                edge_count / (no_of_nodes * (no_of_nodes - 1) / 2)
            )
        inter_edge_ratio = []
        for c1_name, c2_name in self.cluster_edges:
            edge_count = 0
            c1_no_of_nodes = len(self.cluster_mapping[c1_name])
            c2_no_of_nodes = len(self.cluster_mapping[c2_name])
            for n1 in self.cluster_mapping[c1_name]:
                n1_name = self.get_node_by_name(n1, self.true_dag)
                n1 = self.true_dag.G.node_map[n1_name]
                for n2 in self.cluster_mapping[c2_name]:
                    n2_name = self.get_node_by_name(n2, self.true_dag)
                    n2 = self.true_dag.G.node_map[n2_name]
                    if n1 in self.true_dag.neighbors(n2):
                        edge_count += 1
            inter_edge_ratio.append(
                edge_count / (c1_no_of_nodes * c2_no_of_nodes)
            )
        inter_edge_ratio_with_disconnected_clust = []
        for c1_name, c2_name in combinations(self.cluster_mapping.keys(), 2):
            if (c1_name, c2_name) not in self.cluster_edges:
                inter_edge_ratio_with_disconnected_clust.append(0)
            else:
                edge_count = 0
                c1_no_of_nodes = len(self.cluster_mapping[c1_name])
                c2_no_of_nodes = len(self.cluster_mapping[c2_name])
                for n1 in self.cluster_mapping[c1_name]:
                    n1_name = self.get_node_by_name(n1, self.true_dag)
                    n1 = self.true_dag.G.node_map[n1_name]
                    for n2 in self.cluster_mapping[c2_name]:
                        n2_name = self.get_node_by_name(n2, self.true_dag)
                        n2 = self.true_dag.G.node_map[n2_name]
                        if n1 in self.true_dag.neighbors(n2):
                            edge_count += 1
                inter_edge_ratio_with_disconnected_clust.append(
                    edge_count / (c1_no_of_nodes * c2_no_of_nodes)
                )
        return (
            np.mean(intra_edge_ratio),
            np.mean(inter_edge_ratio),
            np.mean(inter_edge_ratio_with_disconnected_clust),
        )