import causallearn
import castle
import numpy as np
import itertools
import networkx as nx
import copy

from typing import List, Dict, Tuple

from causallearn.graph.GraphClass import CausalGraph
from causallearn.graph.Endpoint import Endpoint
from causallearn.graph.Edge import Edge
from causallearn.graph.Node import Node

from castle.datasets.simulator import IIDSimulation, DAG

from clustercausal.clusterdag.ClusterDAG import ClusterDAG


class Simulator:
    """
    A simulator to generate a causal graph and data from it.
    Arguments:
        true_dag: the true causal graph(needs weighted_adjacency_matrix)
        n_nodes: number of nodes in the true_dag if simulated
        n_edges: number of edges in the true_dag if simulated
        dag_method: method to generate the causal graph,
                    methods supported: erdos_renyi, scale_free, bipartite, hierarchical
                    not supported: low_rank
        n_clusters: number of clusters in the cluster graph, if None then random
        n_c_edges: number of edges in the cluster graph, if None then random
                    is only used when dag_method is 'cdag'
        weight_range: range of weights of adjacency matrix in the causal graph
        distribution_type: distribution type of the data
                    methods supported:
                        gauss, exp, gumbel, uniform, logistic (linear);
                        mlp, mim, gp, gp-add, quadratic (nonlinear).
        scm_method: linear or nonlinear, default is linear
        sample_size: size of the data
        seed: seed for the random number generator
        noise_scale: scale of the noise in the data
    """

    def __init__(
        self,
        true_dag=None,
        n_nodes=7,
        n_edges=13,
        dag_method="erdos_renyi",
        cluster_method="dag",
        n_clusters=None,
        n_c_edges=None,
        weight_range=[-1, 2],
        distribution_type="gauss",
        scm_method="linear",
        sample_size=10000,
        seed=42,
        node_names=None,
        noise_scale=1.0,
        alpha=0.05,
    ):
        """
        Initialize an instance, set parameters
        """
        self.true_dag = true_dag
        self.n_nodes = n_nodes
        self.n_edges = n_edges
        print("Warning: n_edges is not exact due to gcastle implementation")
        self.dag_method = dag_method
        self.cluster_method = cluster_method
        self.n_clusters = n_clusters
        self.n_c_edges = n_c_edges
        self.weight_range = tuple(weight_range)
        self.distribution_type = distribution_type
        self.scm_method = scm_method
        self.sample_size = sample_size
        self.seed = seed
        self.node_names = node_names
        self.noise_scale = noise_scale
        self.alpha = alpha

    def run(self) -> ClusterDAG:
        """
        Run the simulator and generate a cluster_dag
        'Arguments':
            cluster_method: 'standard' or 'cluster'
                Decides if C-DAG or DAG is generated first
                'dag': generated DAG and uses topological ordering to cluster
                'cdag': generates clusters and drops out edges in and between
                            clusters
        Returns:
            cluster_dag: a ClusterDAG object
                with true_dag, data, cluster_graph, cluster_mapping attributes
        """
        dag = self.true_dag
        if self.n_clusters is None:
            np.random.seed(self.seed)
            self.n_clusters = np.random.randint(
                low=2, high=int(np.ceil(self.n_nodes / 2)) + 1
            )
        if self.cluster_method == "dag":
            if dag is None:
                dag = self.generate_dag(
                    self.n_nodes,
                    self.n_edges,
                    self.dag_method,
                    self.weight_range,
                    self.seed,
                    self.node_names,
                )
            cluster_dag = self.generate_clustering(
                dag, self.n_clusters, self.seed
            )
        elif self.cluster_method == "cdag":
            if dag is None:
                cluster_dag = self.generate_dag_via_clusters(
                    self.n_clusters,
                    self.n_c_edges,
                    self.n_nodes,
                    self.n_edges,
                    self.dag_method,
                    self.seed,
                    self.weight_range,
                    node_names=None,
                )

        # adj_dag, cluster_graph, cluster_mapping = self.generate_clustering(
        #     dag, self.n_clusters, self.n_c_edges, self.dag_method, self.seed
        # )
        data = self.generate_data(
            cluster_dag.true_dag,
            self.sample_size,
            self.distribution_type,
            self.scm_method,
            self.noise_scale,
        )

        # cluster_edges = []
        # for edge in cluster_graph.G.get_graph_edges():
        #     node1_name = edge.get_node1().get_name()
        #     node2_name = edge.get_node2().get_name()
        #     cluster_edges.append((node1_name, node2_name))

        # Ensure that node names in true_dag and est_dag (calculated later)
        # are the same
        # node_names = [node.get_name() for node in adj_dag.G.get_nodes()]
        # cluster_dag = ClusterDAG(cluster_mapping, cluster_edges, node_names)
        # cluster_dag.true_dag = adj_dag

        cluster_dag.data = data
        return cluster_dag

    def run_with_latents(self, no_of_latent_vars = None) -> ClusterDAG:
        """
        Runs the simulator and generates a cluster_dag. 
        Adds latent variables by adding extra ones and removing them. 
        'dag' is not really a dag anymore, because of the latent variables.
        'Arguments':
            cluster_method: 'dag'
        Returns:
            cluster_dag: a ClusterDAG object
                with true_dag, data, cluster_graph, cluster_mapping attributes
        """
        if self.cluster_method != "dag":
            raise ValueError("For latent var simulation, cluster_method must be 'dag'")
        # increase nodes + edges by 20% to simulate latent variables, if no
        # number of latent_variables was specified
        if no_of_latent_vars is None:
            no_of_latent_vars = round(self.n_nodes * 0.2)
        ratio = no_of_latent_vars / self.n_nodes
        self.n_nodes += no_of_latent_vars
        self.n_edges += round(self.n_edges * ratio)
            
        dag = self.true_dag

        if dag is None:
            dag = self.generate_dag(
                self.n_nodes,
                self.n_edges,
                self.dag_method,
                self.weight_range,
                self.seed,
                self.node_names,
            )

        data = self.generate_data(
            dag,
            self.sample_size,
            self.distribution_type,
            self.scm_method,
            self.noise_scale,
        )
        # dag.draw_pydot_graph()
        # Remove first 1/3 of nodes and add bidirected edges
        remove_nodes = []
        topological_ordering = self.get_topological_ordering(dag)
        for i in range(no_of_latent_vars):
            # Get children of node
            # node_i = ClusterDAG.get_key_by_value(dag.G.node_map, i)
            node_i = ClusterDAG.get_node_by_name(topological_ordering[i], dag)
            children = dag.G.get_children(node_i) #list of Node objects
            # Add bidirected edges between children
            for node_a, node_b in itertools.combinations(children, 2):
                # Check if an edge already exists between node_a, node_b
                edge = dag.G.get_edge(node_a, node_b)
                a = dag.G.node_map[node_a]
                b = dag.G.node_map[node_b]
                # if edge was pointing left, causallearn flips it..
                # so we flip a and b too
                if (edge is not None) and (edge.get_node1() != node_a) and edge.get_node2() != node_b:
                    a, b = b, a
                # Add bidirected edge if edge is none
                if edge is None:
                    # edge = Edge(node_a, node_b, Endpoint.ARROW, Endpoint.ARROW)
                    # edge.set_endpoint1(Endpoint.ARROW)
                    # edge.set_endpoint2(Endpoint.ARROW)
                    # add edge
                    dag.G.graph[a, b] = Endpoint.ARROW.value
                    dag.G.graph[b, a] = Endpoint.ARROW.value
                    # dag.G.add_edge(edge)
                # If edge node_a -> node_b exists, change to -> and <->
                elif edge.get_endpoint1() == Endpoint.TAIL:
                    dag.G.remove_edge(edge)
                    # new_edge = Edge(node_a, node_b, \
                                    # Endpoint.TAIL_AND_ARROW, Endpoint.ARROW_AND_ARROW)
                    # edge.set_endpoint1(Endpoint.TAIL_AND_ARROW)
                    # edge.set_endpoint2(Endpoint.ARROW_AND_ARROW)
                    # dag.G.add_edge(edge)
                    dag.G.graph[a, b] = Endpoint.TAIL_AND_ARROW.value
                    dag.G.graph[b, a] = Endpoint.ARROW_AND_ARROW.value
                # If edge node_a <- node_b exists, change to <- and <->
                elif edge.get_endpoint1() == Endpoint.ARROW:
                    dag.G.remove_edge(edge)
                    # edge.set_endpoint1(Endpoint.ARROW_AND_ARROW)
                    # edge.set_endpoint2(Endpoint.TAIL_AND_ARROW)
                    # new_edge = Edge(node_a, node_b, \
                    #                 Endpoint.ARROW_AND_ARROW, Endpoint.TAIL_AND_ARROW)
                    # dag.G.add_edge(edge)
                    dag.G.graph[a, b] = Endpoint.ARROW_AND_ARROW.value
                    dag.G.graph[b, a] = Endpoint.TAIL_AND_ARROW.value
            remove_nodes.append(node_i)

        # Remove nodes
        for node in remove_nodes:
            dag.G.remove_node(node)

        # Remove first 1/3 of data
        data = data[:, no_of_latent_vars:]

        # Construct clustering
        if self.n_clusters is None:
            np.random.seed(self.seed)
            self.n_clusters = np.random.randint(
                low=2, high=int(np.ceil(self.n_nodes / 2)) + 1
            )
        cluster_dag = self.generate_clustering_with_latents(
            dag, self.n_clusters, self.seed
        )
        cluster_dag.data = data

        # Get MAG for evaluation
        cluster_dag.true_mag = self.get_mag(cluster_dag.true_dag)

        return cluster_dag

    @staticmethod
    def generate_dag(
        n_nodes, n_edges, dag_method, weight_range, seed, node_names=None
    ) -> CausalGraph:
        """
        Generate a random DAG with gcastle
        Arguments:
            n_nodes: number of nodes in the causal graph
            n_edges: number of edges in the causal graph
            dag_method: method to generate the causal graph]
                    methods supported: erdos_renyi, scale_free, bipartite, hierarchical
                    not supported: low_rank
            seed: seed for the random number generator
        Output:
            A CausalGraph object
        """
        if dag_method == "erdos_renyi":
            W = DAG.erdos_renyi(
                n_nodes,
                n_edges,
                weight_range=weight_range,
                seed=seed,
            )
        elif dag_method == "scale_free":
            W = DAG.scale_free(
                n_nodes,
                n_edges,
                weight_range=weight_range,
                seed=seed,
            )
        elif dag_method == "bipartite":
            W = DAG.bipartite(
                n_nodes,
                n_edges,
                weight_range=weight_range,
                seed=seed,
            )
        elif dag_method == "hierarchical":
            W = DAG.hierarchical(
                n_nodes,
                n_edges,
                weight_range=weight_range,
                seed=seed,
            )
        # elif dag_method == "low_rank":
        #     W = DAG.low_rank(
        #         n_nodes, n_edges, weight_range=weight_range, seed=seed
        #     )
        # for weighted adjacency matrix W create CausalGraph object
        dag = CausalGraph(no_of_var=W.shape[0], node_names=node_names)
        dag.G.graph = np.zeros((W.shape[0], W.shape[1]))
        dag.weighted_adjacency_matrix = W
        for i in range(W.shape[0]):
            for j in range(W.shape[1]):
                if W[i, j] != 0:
                    # Make tail at i and arrow at j
                    dag.G.graph[i, j] = -1
                    dag.G.graph[j, i] = 1
        return dag

    @staticmethod
    def generate_dag_via_clusters(
        n_clusters,
        n_c_edges,
        n_nodes,
        n_edges,
        dag_method,
        seed,
        weight_range,
        node_names=None,
    ):
        """
        Generates a random C-DAG with gcastle and then
        drops out edges from the mpdag to generate a DAG
        Arguments:
            n_clusters: number of clusters in the C-DAG
            n_c_edges: not exact, if None then roughly 1.2 * n_nodes
            n_nodes: number of nodes in the DAG
            n_edges: influences number of edges in the DAG
            dag_method: method to generate the C-DAG
                    methods supported: erdos_renyi, scale_free, hierarchical
            seed: seed for the random number generator
            weight_range: range of weights of adjacency matrix for the DAG
            node_names: names of the nodes in the DAG
        returns:
            cluster_dag: a CausalGraph object
            cluster_dag.true_dag; the true DAG
        """
        if n_c_edges is None:
            n_c_edges = np.round(n_nodes * 1.2)
        # Simpler for gridsearches, always use erdos_renyi for cluster graph
        W_clust = DAG.erdos_renyi(
            n_clusters,
            n_c_edges,
            weight_range=weight_range,
            seed=seed,
        )
        # if dag_method == "erdos_renyi":
        #     W_clust = DAG.erdos_renyi(
        #         n_clusters,
        #         n_c_edges,
        #         weight_range=weight_range,
        #         seed=seed,
        #     )
        # elif dag_method == "scale_free":
        #     W_clust = DAG.scale_free(
        #         n_clusters,
        #         n_c_edges,
        #         weight_range=weight_range,
        #         seed=seed,
        #     )
        # elif dag_method == "bipartite":
        #     W = DAG.bipartite(
        #         n_clusters,
        #         n_c_edges,
        #         weight_range=weight_range,
        #         seed=seed,
        #     )
        # elif dag_method == "hierarchical":
        #     W = DAG.hierarchical(
        #         n_clusters,
        #         n_c_edges,
        #         weight_range=weight_range,
        #         seed=seed,
        #     )
        # elif dag_method == "low_rank":
        #     W = DAG.low_rank(
        #         n_nodes, n_edges, weight_range=weight_range, seed=seed
        #     )
        # for weighted adjacency matrix W create CausalGraph object

        cluster_names = [f"C{i+1}" for i in range(n_clusters)]
        cluster_graph = CausalGraph(
            no_of_var=W_clust.shape[0], node_names=cluster_names
        )
        cluster_graph.G.graph = np.zeros((W_clust.shape[0], W_clust.shape[1]))
        for i in range(W_clust.shape[0]):
            for j in range(W_clust.shape[1]):
                if W_clust[i, j] != 0:
                    # Make tail at i and arrow at j
                    cluster_graph.G.graph[i, j] = -1
                    cluster_graph.G.graph[j, i] = 1

        if node_names is None:
            node_names = [f"X{i+1}" for i in range(n_nodes)]
        # Partition nodes into clusters
        node_range = list(range(1, n_nodes))
        cluster_cutoffs = sorted(
            np.random.choice(node_range, size=n_clusters - 1, replace=False)
        )
        cluster_cutoffs.append(
            n_nodes
        )  # ensure that last cluster has all remaining nodes
        cluster_mapping = {}
        j = 0
        l = 0
        u = cluster_cutoffs[0]
        for cluster in cluster_names:
            cluster_mapping[cluster] = []
            for i in range(l, u):
                cluster_mapping[cluster].append(node_names[i])
            l = u
            if j < n_clusters - 1:
                u = cluster_cutoffs[j + 1]
                j += 1

        # Cluster edges
        cluster_edges = []
        for edge in cluster_graph.G.get_graph_edges():
            c1_name = edge.get_node1().get_name()
            c2_name = edge.get_node2().get_name()
            endpoint1 = edge.get_endpoint1()
            endpoint2 = edge.get_endpoint2()
            if endpoint1 == Endpoint.ARROW and endpoint2 == Endpoint.TAIL:
                if (c2_name, c1_name) not in cluster_edges:
                    cluster_edges.append((c2_name, c1_name))
            if endpoint1 == Endpoint.TAIL and endpoint2 == Endpoint.ARROW:
                if (c1_name, c2_name) not in cluster_edges:
                    cluster_edges.append((c1_name, c2_name))
                # if (endpoint1 == Endpoint.TAIL_AND_ARROW or endpoint1 == Endpoint.ARROW_AND_ARROW) \
                #         and (endpoint2 == Endpoint.TAIL_AND_ARROW or endpoint2 == Endpoint.ARROW_AND_ARROW):
                #     cluster_edges.append((c1_name, c2_name))
                #     cluster_edges.append((c2_name, c1_name)) # Later for confounders

        cluster_dag = ClusterDAG(
            cluster_mapping, cluster_edges, node_names=node_names
        )

        # Generate DAG and adjacency matrix
        # Probability of keeping edges, influenced by n_edges
        p_intra = 3 * (n_edges / (n_nodes * (n_nodes - 1)))
        p_inter = 1.5 * (n_edges / (n_nodes * (n_nodes - 1)))
        cluster_dag.cdag_to_mpdag()
        cluster_dag.true_dag = cluster_dag.cg
        # For pseudo-rng
        if seed is not None:
            np.random.seed(seed)
            p_list = np.random.rand(1000)
            p_i = 0
        for edge in cluster_dag.true_dag.G.get_graph_edges():
            node1_name = edge.get_node1().get_name()
            node2_name = edge.get_node2().get_name()
            c1_name = ClusterDAG.find_key(cluster_mapping, node1_name)
            c2_name = ClusterDAG.find_key(cluster_mapping, node2_name)
            if c1_name == c2_name:
                # make pseudo-rng or real rng
                if seed is not None:
                    p = p_list[p_i]
                    if p_i == 999:
                        p_i = 0
                    else:
                        p_i += 1
                else:
                    p = np.random.uniform()
                # Drop edge out with probability (1- p_intra)
                if p > p_intra:
                    cluster_dag.true_dag.G.remove_edge(edge)
                else:  # Orient edge according to node_names ordering
                    if node_names.index(node1_name) < node_names.index(
                        node2_name
                    ):
                        cluster_dag.true_dag.G.remove_edge(edge)
                        edge.set_endpoint1(Endpoint.TAIL)
                        edge.set_endpoint2(Endpoint.ARROW)
                        cluster_dag.true_dag.G.add_edge(edge)
                    else:
                        cluster_dag.true_dag.G.remove_edge(edge)
                        edge.set_endpoint1(Endpoint.ARROW)
                        edge.set_endpoint2(Endpoint.TAIL)
                        cluster_dag.true_dag.G.add_edge(edge)
            elif (
                c1_name != c2_name
                and ((c1_name, c2_name) or (c2_name, c1_name)) in cluster_edges
            ):
                # Drop edge out with probability (1- p_inter)
                # Drop edge out with probability (1- p_intra)
                np.random.seed(seed)
                p = np.random.uniform()
                if p > p_inter:
                    cluster_dag.true_dag.G.remove_edge(edge)
                # Edge is already oriented
        # Make true_dag adjacency matrix
        np.random.seed(seed)
        weight_range_top = weight_range[1] - weight_range[0]
        W = (
            weight_range_top * np.random.rand(len(node_names), len(node_names))
            + weight_range[0]
        )
        cluster_dag.true_dag.weighted_adjacency_matrix = np.zeros(
            (len(node_names), len(node_names))
        )
        for i in range(len(node_names)):
            for j in range(len(node_names)):
                # set weight[i,j] if edge i-->j exists
                if (
                    cluster_dag.true_dag.G.graph[i, j] == -1
                    and cluster_dag.true_dag.G.graph[j, i] == 1
                ):
                    cluster_dag.true_dag.weighted_adjacency_matrix[i, j] = W[
                        i, j
                    ]

        return cluster_dag

    @staticmethod
    def generate_data(
        dag: CausalGraph,
        sample_size,
        distribution_type,
        scm_method,
        noise_scale,
    ):
        """
        Generate data from the causal graph
        Arguments:
            dag: the causal graph
            sample_size: size of the data
            distribution_type: distribution type of the data
                    methods supported:
                        gauss, exp, gumbel, uniform, logistic (linear);
                        lmp, mim, gp, gp-add, quadratic (nonlinear).
            scm_method: linear or nonlinear, default is linear
            noise_scale: scale of the noise in the data
        Output:
            data: sample_size x no_of_nodes ndarray
        """
        if dag.weighted_adjacency_matrix is None:
            raise ValueError("Adjacency matrix is None")
        dataset = IIDSimulation(
            dag.weighted_adjacency_matrix,
            n=sample_size,
            method=scm_method,
            sem_type=distribution_type,
            noise_scale=noise_scale,
        )
        return dataset.X

    @staticmethod
    def generate_clustering(dag: CausalGraph, n_clusters, seed):
        """
        Generate an admissible (no cycles) clustering from dag
        Arguments:
            dag: the causal graph
            n_clusters: number of clusters in the cluster graph, if None then random
            n_c_edges: number of edges in the cluster graph, if None then random
            dag_method: method to generate the causal graph
                    methods supported: erdos_renyi, scale_free, bipartite, hierarchical
                    not supported: low_rank
            seed: seed for the random number generator
        Output:
            cluster_dag: a ClusterDAG object
        Adjusts true_dag such that cluster_graph is admissible
        """

        # Generate a cluster graph
        n_nodes = dag.G.graph.shape[0]
        np.random.seed(seed)
        node_names = [node.get_name() for node in dag.G.get_nodes()]

        # Get topological ordering of nodes, based on that generate admissible cluster graph
        nx_helper_graph = nx.DiGraph()
        edge_name_list = []
        for edge in dag.G.get_graph_edges():
            node1_name = edge.get_node1().get_name()
            node2_name = edge.get_node2().get_name()
            edge_name_list.append((node1_name, node2_name))
        nx_helper_graph.add_edges_from(edge_name_list)
        nx_helper_graph.add_nodes_from(
            node_names
        )  # ensure that all nodes are in the graph
        topological_ordering = list(nx.topological_sort(nx_helper_graph))
        # successively partition the topological ordering into clusters
        # Each cluster gets at least one node
        # Get cluster cutoffs by drawing without replacement from topological ordering
        node_range = list(range(1, n_nodes))
        cluster_cutoffs = sorted(
            np.random.choice(node_range, size=n_clusters - 1, replace=False)
        )
        cluster_cutoffs.append(
            n_nodes
        )  # ensure that last cluster has all remaining nodes
        cluster_mapping = {}
        cluster_names = [f"C{i+1}" for i in range(n_clusters)]
        j = 0
        l = 0
        u = cluster_cutoffs[0]
        for cluster in cluster_names:
            cluster_mapping[cluster] = []
            for i in range(l, u):
                cluster_mapping[cluster].append(topological_ordering[i])
            l = u
            if j < n_clusters - 1:
                u = cluster_cutoffs[j + 1]
                j += 1

        # Cluster edges
        cluster_edges = []
        for edge in dag.G.get_graph_edges():
            node1_name = edge.get_node1().get_name()
            node2_name = edge.get_node2().get_name()
            c1_name = ClusterDAG.find_key(cluster_mapping, node1_name)
            c2_name = ClusterDAG.find_key(cluster_mapping, node2_name)
            if c1_name != c2_name:
                endpoint1 = edge.get_endpoint1()
                endpoint2 = edge.get_endpoint2()
                if endpoint1 == Endpoint.ARROW and endpoint2 == Endpoint.TAIL:
                    if (c2_name, c1_name) not in cluster_edges:
                        cluster_edges.append((c2_name, c1_name))
                if endpoint1 == Endpoint.TAIL and endpoint2 == Endpoint.ARROW:
                    if (c1_name, c2_name) not in cluster_edges:
                        cluster_edges.append((c1_name, c2_name))
                # if (endpoint1 == Endpoint.TAIL_AND_ARROW or endpoint1 == Endpoint.ARROW_AND_ARROW) \
                #         and (endpoint2 == Endpoint.TAIL_AND_ARROW or endpoint2 == Endpoint.ARROW_AND_ARROW):
                #     cluster_edges.append((c1_name, c2_name))
                #     cluster_edges.append((c2_name, c1_name)) # Later for confounders

        cluster_dag = ClusterDAG(
            cluster_mapping, cluster_edges, node_names=node_names
        )
        cluster_dag.true_dag = dag
        return cluster_dag
    
    @staticmethod
    def generate_clustering_with_latents(dag: CausalGraph, n_clusters, seed):
        """
        Generate an admissible (no cycles) clustering from dag. Supports latent
        variables. 
        Arguments:
            dag: the causal graph
            n_clusters: number of clusters in the cluster graph, if None then random
            seed: seed for the random number generator
        Output:
            cluster_dag: a ClusterDAG object
        Adjusts true_dag such that cluster_graph is admissible
        """
        
        # Generate a cluster graph
        n_nodes = dag.G.graph.shape[0]
        np.random.seed(seed)
        node_names = [node.get_name() for node in dag.G.get_nodes()]

        # Get topological ordering of nodes (only directed edges necessary)
        nx_helper_graph = nx.DiGraph()
        edge_name_list = []
        for edge in dag.G.get_graph_edges():
            points_right = (edge.get_endpoint1() == Endpoint.TAIL) and (edge.get_endpoint2() == Endpoint.ARROW)
            points_left = (edge.get_endpoint1() == Endpoint.ARROW) and (edge.get_endpoint2() == Endpoint.TAIL)
            is_directed_edge = points_right or points_left
            if is_directed_edge:
                node1_name = edge.get_node1().get_name()
                node2_name = edge.get_node2().get_name()
                if points_right:
                    edge_name_list.append((node1_name, node2_name))
                if points_left:
                    edge_name_list.append((node2_name, node1_name))
        nx_helper_graph.add_edges_from(edge_name_list)
        nx_helper_graph.add_nodes_from(
            node_names
        )  # ensure that all nodes are in the graph
        import matplotlib.pyplot as plt
        # nx.draw(nx_helper_graph, with_labels=True)
        # nx.draw_networkx(nx_helper_graph, with_labels=True, arrowsize = 60, node_size = 7000, font_size = 50)
        # plt.show()
        topological_ordering = list(nx.topological_sort(nx_helper_graph))
        # successively partition the topological ordering into clusters
        # Each cluster gets at least one node
        # Get cluster cutoffs by drawing without replacement from topological ordering
        node_range = list(range(1, n_nodes))
        cluster_cutoffs = sorted(
            np.random.choice(node_range, size=n_clusters - 1, replace=False)
        )
        cluster_cutoffs.append(
            n_nodes
        ) # ensure that last cluster has all remaining nodes

        cluster_mapping = {}
        cluster_names = [f"C{i+1}" for i in range(n_clusters)]
        j = 0
        l = 0
        u = cluster_cutoffs[0]
        for cluster in cluster_names:
            cluster_mapping[cluster] = []
            for i in range(l, u):
                cluster_mapping[cluster].append(topological_ordering[i])
            l = u
            if j < n_clusters - 1:
                u = cluster_cutoffs[j + 1]
                j += 1

        # Cluster edges
        cluster_edges = []
        cluster_bidirected_edges = []
        for edge in dag.G.get_graph_edges():
            node1_name = edge.get_node1().get_name()
            node2_name = edge.get_node2().get_name()
            c1_name = ClusterDAG.find_key(cluster_mapping, node1_name)
            c2_name = ClusterDAG.find_key(cluster_mapping, node2_name)
            if c1_name != c2_name:
                endpoint1 = edge.get_endpoint1()
                endpoint2 = edge.get_endpoint2()
                # Add edge <-
                if endpoint1 == Endpoint.ARROW and endpoint2 == Endpoint.TAIL:
                    if (c2_name, c1_name) not in cluster_edges:
                        cluster_edges.append((c2_name, c1_name))
                # Add edge ->
                if endpoint1 == Endpoint.TAIL and endpoint2 == Endpoint.ARROW:
                    if (c1_name, c2_name) not in cluster_edges:
                        cluster_edges.append((c1_name, c2_name))
                # Add edges <-> and <-
                if endpoint1 == Endpoint.ARROW_AND_ARROW and endpoint2 == Endpoint.TAIL_AND_ARROW:
                    if ((c1_name, c2_name) or (c2_name, c1_name)) not in cluster_bidirected_edges:
                        cluster_bidirected_edges.append((c1_name, c2_name))
                    if (c2_name, c1_name) not in cluster_edges:
                        cluster_edges.append((c2_name, c1_name))
                # Add edges <-> and ->
                if endpoint1 == Endpoint.TAIL_AND_ARROW and endpoint2 == Endpoint.ARROW_AND_ARROW:
                    if ((c1_name, c2_name) or (c2_name, c1_name)) not in cluster_bidirected_edges:
                        cluster_bidirected_edges.append((c1_name, c2_name))
                    if (c1_name, c2_name) not in cluster_edges:
                        cluster_edges.append((c1_name, c2_name))
                # Add edge <->
                if endpoint1 == Endpoint.ARROW and endpoint2 == Endpoint.ARROW:
                    if (c1_name, c2_name) not in cluster_bidirected_edges:
                        cluster_bidirected_edges.append((c1_name, c2_name))
        
        cluster_dag = ClusterDAG(
            cluster_mapping, cluster_edges, cluster_bidirected_edges, node_names=node_names
        )

        cluster_dag.true_dag = dag
        return cluster_dag
    
    @staticmethod
    def get_topological_ordering(dag: CausalGraph):
        """
        Returns topological ordering of nodes from 'dag'. 
        Returns:
            - topological_ordering: list of node names in topological order
        """
        nx_helper_graph = nx.DiGraph()
        node_names = [node.get_name() for node in dag.G.nodes]

        edge_name_list = []
        for edge in dag.G.get_graph_edges():
            node1_name = edge.get_node1().get_name()
            node2_name = edge.get_node2().get_name()
            edge_name_list.append((node1_name, node2_name))
        nx_helper_graph.add_edges_from(edge_name_list)
        nx_helper_graph.add_nodes_from(
            node_names
        )  # ensure that all nodes are in the graph
        topological_ordering = list(nx.topological_sort(nx_helper_graph))
        return topological_ordering
    
    @staticmethod
    def get_mag(dag: CausalGraph) -> CausalGraph:
        """
        Finds inducing paths and adds edges to make it a maximal ancestral graph. 
        This graph serves as ground truth for causal discovery. 
        """
        mag = copy.deepcopy(dag)
        ###     Find inducing paths      ###
        
        # First find all bidirected paths 
        bidirected_paths = {}
        for node in mag.G.nodes:
            bidirected_paths[node] = [[node]]
        for i in range(len(mag.G.nodes) + 1):
            for node in mag.G.nodes:
                for bidir_path in bidirected_paths[node]:
                    if len(bidir_path) != i + 1:
                        continue
                    last_node = bidir_path[-1]
                    edges = mag.G.get_node_edges(last_node)
                    for edge in edges:
                        if Simulator.edge_is_bidirected(edge):
                            next_node = edge.get_node2()
                            if next_node == last_node:
                                # Check that edge wasn't flipped by causallearn
                                next_node = edge.get_node1()
                            bidirected_paths[node].append(bidir_path + [next_node])

        # Second find all collider paths
        collider_paths = copy.deepcopy(bidirected_paths)
        for node in bidirected_paths.keys():
            parents = mag.G.get_parents(node)
            for bidir_path in bidirected_paths[node]:
                for parent in parents:
                    if parent not in bidir_path:
                        collider_paths[node].append([parent] + bidir_path)
                last_node = bidir_path[-1]
                children = mag.G.get_children(last_node)
                for child in children:
                    if child not in bidir_path:
                        collider_paths[node].append(bidir_path + [child])

        # Third find all ancestors for every node
        ancestors_dict = {}
        for node in mag.G.nodes:
            ancestors: List[Node] = []
            mag.G.collect_ancestors(node, ancestors)
            ancestors_dict[node] = ancestors

        # Fourth for collider paths with 3 or more clusters, 
        # check for inducing paths and add edge if found
        for node in collider_paths.keys():
            for collider_path in collider_paths[node]:
                inducing_path = True
                if len(collider_path) < 3:
                    continue
                start_node = collider_path[0]
                end_node = collider_path[-1]
                for coll_node in collider_path[1:-1]:
                    if (coll_node in ancestors_dict[start_node]) or \
                        (coll_node in ancestors_dict[end_node]):
                        pass 
                    else:
                        inducing_path = False
                        break
                # If we're here, we have an inducing path
                inducing_path_names = [node.get_name() for node in collider_path]
                print(f"Inducing path found: {inducing_path_names}")
                # Have to add ->, <- or <-> between
                # start_node and end_node, depending on the ancestorship
                i = mag.G.node_map[start_node]
                j = mag.G.node_map[end_node]
                if start_node in ancestors_dict[end_node]:
                    # Add edge start_node -> end_node
                    mag.G.graph[i, j] = Endpoint.TAIL.value
                    mag.G.graph[j, i] = Endpoint.ARROW.value
                elif end_node in ancestors_dict[start_node]:
                    # Add edge start_node <- end_node
                    mag.G.graph[i, j] = Endpoint.ARROW.value
                    mag.G.graph[i, j] = Endpoint.TAIL.value
                else:
                    # Add edge start_node <-> end_node
                    mag.G.graph[i, j] = Endpoint.ARROW.value
                    mag.G.graph[j, i] = Endpoint.ARROW.value

        # Remove almost directed cycles, <-> to ->
        for node in mag.G.nodes:
            ancestors: List[Node] = []
            mag.G.collect_ancestors(node, ancestors)
            # Check if node <-> ancestor
            for ancestor in ancestors:
                edge = mag.G.get_edge(ancestor, node)
                if edge: # edge is either -> and <-> or ->
                    if edge.get_endpoint1() == Endpoint.TAIL_AND_ARROW and \
                        edge.get_endpoint2() == Endpoint.ARROW_AND_ARROW:
                        i = mag.G.node_map[ancestor]
                        j = mag.G.node_map[node]
                        # Remove edge and set to ->
                        mag.G.remove_edge(edge)
                        mag.G.graph[i, j] = Endpoint.TAIL.value
                        mag.G.graph[j, i] = Endpoint.ARROW.value
        return mag
    
    @staticmethod
    def edge_is_bidirected(edge: Edge) -> bool:
        """
        Checks if edge is bidirected, i.e. <-> or <-> and ->/ <-. 
        """
        if edge.get_endpoint1() == Endpoint.ARROW and edge.get_endpoint2() == Endpoint.ARROW:
            return True
        if edge.get_endpoint1() == Endpoint.TAIL_AND_ARROW and edge.get_endpoint2() == Endpoint.ARROW_AND_ARROW:
            return True
        if edge.get_endopint1() == Endpoint.ARROW_AND_ARROW and edge.get_endpoint2() == Endpoint.TAIL_AND_ARROW:
            return True
        return False
