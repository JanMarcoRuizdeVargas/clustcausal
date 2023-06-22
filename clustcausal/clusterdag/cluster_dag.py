import numpy as np
import pandas as pd
import networkx as nx
import causallearn
import castle
import pydot
import logging

from itertools import combinations
from causallearn.graph.GraphClass import CausalGraph
from causallearn.utils.PCUtils.BackgroundKnowledge import BackgroundKnowledge

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class CDAG:
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
    def __init__(self, cluster_mapping: dict, 
        cluster_edges: list):
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
        self.cluster_mapping = cluster_mapping
        self.cluster_edges = cluster_edges
        self.node_names = []
        for cluster in self.cluster_mapping:
            self.node_names.extend(self.cluster_mapping[cluster])
        self.node_indices = {} # Dictionary that points to which cluster the node is in
        for node in self.node_names:
            for cluster, vertice in self.cluster_mapping.items():
                if node in vertice:
                    self.node_indices[node] = cluster
        self.cluster_graph = CausalGraph(no_of_var = len(self.cluster_mapping),
                                node_names = list(self.cluster_mapping.keys()))
        for edge in self.cluster_graph.G.get_graph_edges():
            cluster1 = edge.get_node1()
            cluster2 = edge.get_node2()
            cluster1_name = cluster1.get_name()
            cluster2_name = cluster2.get_name()
            if cluster1 != cluster2:
                if (cluster1_name, cluster2_name) not in self.cluster_edges:
                    self.cluster_graph.G.remove_edge(edge)
                    logging.info(f'removed edge: ({cluster1.get_name()},{cluster2.get_name()})')
                if (cluster1_name, cluster2_name) in self.cluster_edges:
                    self.cluster_graph.G.remove_edge(edge)
                    self.cluster_graph.G.add_directed_edge(cluster1, cluster2)
                    logging.info(f'oriented edge: ({cluster1.get_name()},{cluster2.get_name()})')
        

    def cdag_to_mpdag(self) -> CausalGraph:
        """
        Constructs a MPDAG from a CDAG and stores it in a causallearn
        BackgroundKnowledge object. 
        """
        # Create the list of node_names needed for CausalGraph
        self.cg = CausalGraph(no_of_var = len(self.node_names), 
                                                      node_names = self.node_names)
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
                    logging.info(f'removed edge: ({node1.get_name()},{node2.get_name()})')
                if (cluster1, cluster2) in self.cluster_edges:
                    self.cg.G.remove_edge(edge)
                    self.cg.G.add_directed_edge(node1, node2)
                    logging.info(f'oriented edge: ({node1.get_name()},{node2.get_name()})')
        return self.cg

    def draw_cluster_graph(self):
        """
        Draws the cluster DAG using causallearn visualization
        """
        self.cluster_graph.draw_pydot_graph()

    def get_topological_ordering(self):
        """
        Calculates a topological ordering of the CDAG
        and saves it to self.cdag_topological_sort and 
        self.cdag_list_of_topological_sort
        """
        nx_helper_graph = nx.DiGraph()
        nx_helper_graph.add_edges_from(self.cluster_edges)
        self.nx_helper_graph = nx_helper_graph
        self.cdag_topological_sort = nx.topological_sort(nx_helper_graph)
        self.cdag_list_of_topological_sort = list(self.cdag_topological_sort)
        return self.cdag_list_of_topological_sort
    
    def get_parents_plus(self, cluster):
        """
        Gets the pa+ set of a cluster, i.e. the cluster union the parents
        Parameters:
        cluster (Node object in the CausalGraph instance cdag.cluster_graph
        Returns: 
        Tuple of
        TODO
        """
        relevant_clusters = [cluster]
        relevant_clusters.extend(self.cdag.cluster_graph.G.get_parents(cluster))
        for clust in relevant_clusters:
            relevant_clusters[i] = relevant_clusters[i].get_name()
        relevant_nodes_id = cluster.get_name()
        for clust in relevant_clusters:
            relevant_nodes_id.extend(self.cdag.cluster_mapping[clust])
        # Put relevant nodes in a dictionary with id as key and Node object as value
        # self.cdag.cg.G.node_map is the inverse, i.e. with all Node objects as keys 
        # and id as value
        relevant_nodes = {}
        for i in relevant_nodes_id:
            relevant_nodes[i] = ClustPC.get_key_by_value(self.cdag.cg.G.node_map, i)
    
    def get_local_graph(self, cluster):
        """
        Define the local graph on which to run the intra cluster phase, restrict data
        to cluster union parents of cluster
        Parameters:
        cluster (Node object in the CausalGraph instance cdag.cluster_graph
        Returns:
        A GeneralGraph object, restricted to the relevant nodes (cluster union parents)
        TODO
        """
                
        local_data = self.data[:,list(relevant_nodes.keys())] 
        local_graph = self.cdag.cg.G.subgraph(list(relevant_nodes.values()))
    
    def max_degree_of_cluster_nodes_including_parents(self, cluster):
        """
        Returns the maximum degree of the nodes in the cluster in the
        local graph, which includes parents of the cluster.
        Needed for stopping depth of PC algorithm. 
        TODO
        """
        cluster_nodes = self.cluster_mapping[cluster]

    @staticmethod
    def get_key_by_value(dictionary, value):
        # Helper function to get Node object from node_map value i regarding GraphNode object
        for key, val in dictionary.items():
            if val == value:
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