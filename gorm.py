from pickle import Pickler, Unpickler
from json import dumps as jsonned
from json import loads as unjsonned
from StringIO import StringIO
from graph import (
    Graph,
    DiGraph,
    MultiGraph,
    MultiDiGraph
)


def pickled(v):
    io = StringIO()
    pck = Pickler(io)
    pck.dump(v)
    r = io.getvalue()
    io.close()
    return r


def unpickled(s):
    io = StringIO(s)
    upck = Unpickler(io)
    r = upck.load()
    io.close()
    return r


class ORM(object):
    str2type = {
        'bool': bool,
        'int': int,
        'float': float,
        'str': str,
        'unicode': unicode
    }
    type2str = {
        bool: 'bool',
        int: 'int',
        float: 'float',
        str: 'str',
        unicode: 'unicode'
    }
    sql_types = {
        'sqlite': {
            'text': 'TEXT',
            'integer': 'INTEGER',
            'boolean': 'BOOLEAN',
            'true': '1',
            'false': '0'
        }
    }
    def __init__(
            self,
            connector=None,
            sql_flavor='sqlite',
            pickling=False
    ):
        self.pickling = pickling
        if sql_flavor not in self.sql_types:
            raise ValueError("Unknown SQL flavor")
        self.sql_flavor = sql_flavor
        if connector is None:
            from sqlite3 import connect
            self.connection = connect(':memory:')
        else:
            self.connection = connector
        self.cursor = self.connection.cursor()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @property
    def branch(self):
        self.cursor.execute(
            "SELECT value FROM global WHERE key='branch';"
        )
        return self.cursor.fetchone()[0]

    @branch.setter
    def branch(self, v):
        self.cursor.execute(
            "UPDATE global SET value=? WHERE key='branch';",
            (v,)
        )

    @property
    def rev(self):
        self.cursor.execute(
            "SELECT value FROM global WHERE key='rev';"
        )
        return int(self.cursor.fetchone()[0])

    @rev.setter
    def rev(self, v):
        # first make sure the cursor is not before the start of this branch
        branch = self.branch
        self.cursor.execute(
            "SELECT parent, parent_rev FROM branches WHERE branch=?;",
            (branch,)
        )
        (parent, parent_rev) = self.cursor.fetchone()
        if v < int(parent_rev):
            raise ValueError(
                "The revision number {revn} "
                "occurs before the start of "
                "the branch {brnch}".format(revn=v, brnch=branch)
            )
        self.cursor.execute(
            "UPDATE global SET value=? WHERE key='rev';",
            (v,)
        )

    def close(self):
        # maybe these should be in the opposite order?
        self.connection.commit()
        self.cursor.close()

    def initdb(self):
        tabdecls = [
            "CREATE TABLE global ("
            "key {text} NOT NULL, "
            "value {text}, "
            "type {text} NOT NULL, "
            "PRIMARY KEY (key), "
            "CHECK(type IN "
            "('pickle', 'json', 'str', 'unicode', 'int', 'float', 'bool', 'unset'))"
            ");",
            "CREATE TABLE branches ("
            "branch {text} NOT NULL DEFAULT 'master', "
            "parent {text} NOT NULL DEFAULT 'master', "
            "parent_rev {integer} NOT NULL DEFAULT 0, "
            "PRIMARY KEY(branch), "
            "FOREIGN KEY(parent) REFERENCES branch(branch)"
            ");",
            "CREATE TABLE graphs ("
            "graph {text} NOT NULL, "
            "type {text} NOT NULL DEFAULT 'Graph', "
            "PRIMARY KEY(graph), "
            "CHECK(type IN ('Graph', 'DiGraph', 'MultiGraph', 'MultiDiGraph'))"
            ");",
            "INSERT INTO branches DEFAULT VALUES;",
            "CREATE TABLE graph_val ("
            "graph {text} NOT NULL, "
            "key {text} NOT NULL, "
            "branch {text} NOT NULL DEFAULT 'master', "
            "rev {integer} NOT NULL DEFAULT 0, "
            "value {text}, "
            "valtype {text} NOT NULL, "
            "PRIMARY KEY (graph, key, branch, rev), "
            "FOREIGN KEY(graph) REFERENCES graphs(graph), "
            "FOREIGN KEY(branch) REFERENCES branches(branch), "
            "CHECK(valtype IN "
            "('pickle', 'json', 'str', 'unicode', 'int', 'float', 'bool', 'unset'))"
            ");",
            "CREATE TABLE nodes ("
            "graph {text} NOT NULL, "
            "node {text} NOT NULL, "
            "branch {text} NOT NULL DEFAULT 'master', "
            "rev {integer} NOT NULL DEFAULT 0, "
            "extant {boolean} NOT NULL, "
            "nametype {text} NOT NULL DEFAULT 'str', "
            "PRIMARY KEY (graph, node, branch, rev), "
            "FOREIGN KEY(graph) REFERENCES graphs(graph), "
            "FOREIGN KEY(branch) REFERENCES branches(branch), "
            "CHECK(nametype IN ('str', 'int', 'unicode'))"
            ");",
            "CREATE TABLE node_val ("
            "graph {text} NOT NULL, "
            "node {text} NOT NULL, "
            "key {text} NOT NULL, "
            "branch {text} NOT NULL DEFAULT 'master', "
            "rev {integer} NOT NULL DEFAULT 0, "
            "value {text}, "
            "valtype {text} NOT NULL, "
            "PRIMARY KEY(graph, node, key, branch, rev), "
            "FOREIGN KEY(graph, node) REFERENCES nodes(graph, node), "
            "FOREIGN KEY(branch) REFERENCES branches(branch), "
            "CHECK(valtype IN "
            "('pickle', 'json', 'str', 'unicode', 'int', 'float', 'bool', 'unset'))"
            ");",
            "CREATE TABLE edges ("
            "graph {text} NOT NULL, "
            "nodeA {text} NOT NULL, "
            "nodeB {text} NOT NULL, "
            "idx {integer} NOT NULL DEFAULT 0, "
            "branch {text} NOT NULL DEFAULT 'master', "
            "rev {integer} NOT NULL DEFAULT 0, "
            "extant {boolean} NOT NULL, "
            "PRIMARY KEY (graph, nodeA, nodeB, idx, branch, rev), "
            "FOREIGN KEY(graph, nodeA) REFERENCES nodes(graph, node), "
            "FOREIGN KEY(graph, nodeB) REFERENCES nodes(graph, node), "
            "FOREIGN KEY(branch) REFERENCES branches(branch)"
            ");",
            "CREATE TABLE edge_val ("
            "graph {text} NOT NULL, "
            "nodeA {text} NOT NULL, "
            "nodeB {text} NOT NULL, "
            "idx {integer} NOT NULL DEFAULT 0, "
            "key {text}, "
            "branch {text} NOT NULL DEFAULT 'master', "
            "rev {integer} NOT NULL DEFAULT 0, "
            "value {text}, "
            "valtype {text} NOT NULL, "
            "PRIMARY KEY(graph, nodeA, nodeB, idx, key, branch, rev), "
            "FOREIGN KEY(graph, nodeA, nodeB, idx) "
            "REFERENCES edges(graph, nodeA, nodeB, idx), "
            "FOREIGN KEY(branch) REFERENCES branches(branch), "
            "CHECK(valtype IN "
            "('pickle', 'json', 'str', 'unicode', 'int', 'float', 'bool', 'unset'))"
            ");"
        ]
        for decl in tabdecls:
            s = decl.format(**self.sql_types[self.sql_flavor])
            self.cursor.execute(s)
        globs = [
            ("branch", "master", "str"),
            ("rev", 0, "int")
        ]
        self.cursor.executemany(
            "INSERT INTO global (key, value, type) VALUES (?, ?, ?);",
            globs
        )

    def parent(self, branch):
        self.cursor.execute(
            "SELECT branch, parent FROM branches WHERE branch=?;",
            (branch,)
        )
        return self.cursor.fetchone()[1]

    def cast(self, value, typestr):
        """Return ``value`` cast into the type indicated by ``typestr``"""
        if typestr == 'pickle':
            if self.pickling:
                return unpickled(value)
            else:
                raise TypeError(
                    "This value is pickled, but pickling is disabled"
                )
        elif typestr == 'json':
            return unjsonned(value)
        else:
            return self.str2type[typestr](value)

    def stringify(self, value):
        """Return a pair of a string representing the value, and another
        string describing its type (for use with ``cast_value``)

        """
        if type(value) in self.type2str:
            return (value, self.type2str[type(value)])
        try:
            return (jsonned(value), 'json')
        except TypeError:
            if self.pickling:
                return (pickled(value), 'pickle')
            else:
                raise TypeError(
                    "Value isn't serializable without pickling"
                )

    def _init_graph(self, name, type_s='Graph'):
        self.cursor.execute(
            "INSERT INTO graphs (graph, type) VALUES (?, ?);",
            (name, type_s)
        )

    def new_graph(self, name, data=None, **attr):
        self._init_graph(name, 'Graph')
        return Graph(self, name, data, **attr)

    def new_digraph(self, name, data=None, **attr):
        self._init_graph(name, 'DiGraph')
        return DiGraph(self, name, data, **attr)

    def new_multigraph(self, name, data=None, **attr):
        self._init_graph(name, 'MultiGraph')
        return MultiGraph(self, name, data, **attr)

    def new_multidigraph(self, name, data=None, **attr):
        self._init_graph(name, 'MultiDiGraph')
        return MultiDiGraph(self, name, data, **attr)

    def get_graph(self, name):
        self.cursor.execute("SELECT type FROM graphs WHERE graph=?;", (name,))
        try:
            (type_s,) = self.cursor.fetchone()
        except TypeError:
            raise ValueError("I don't know of a graph named {}".format(name))
        return {
            'Graph': Graph,
            'DiGraph': DiGraph,
            'MultiGraph': MultiGraph,
            'MultiDiGraph': MultiDiGraph
        }[type_s](self, name)

    def del_graph(self, name):
        for statement in [
                "DELETE FROM edge_val WHERE graph=?;",
                "DELETE FROM edges WHERE graph=?;",
                "DELETE FROM node_val WHERE graph=?;",
                "DELETE FROM nodes WHERE graph=?;",
                "DELETE FROM graphs WHERE graph=?;"
        ]:
            self.cursor.execute(statement, (name,))

    def _active_branches(self):
        branch = self.branch
        while branch != 'master':
            yield branch
            branch = self.parent(branch)
        yield 'master'

    def _iternodes(self, graph):
        rev = self.rev
        branches = tuple(self._active_branches())
        self.cursor.execute(
            "SELECT nodes.node FROM nodes "
            "JOIN (SELECT graph, node, rev "
            "FROM nodes WHERE graph=? AND rev<=? AND branch IN ({qms}) "
            "GROUP BY graph, node) AS hirev ON "
            "nodes.graph=hirev.graph AND "
            "nodes.node=hirev.node "
            "AND nodes.rev=hirev.rev "
            "AND branch IN ({qms}) "
            "WHERE extant={true};".format(
                qms=", ".join("?" * len(branches)),
                true=self.sql_types[self.sql_flavor]['true']
            ),
            (unicode(graph), rev) + branches * 2
        )
        for row in self.cursor.fetchall():
            try:
                yield int(row[0])
            except ValueError:
                yield row[0]

    def _countnodes(self, graph):
        rev = self.rev
        branches = tuple(self._active_branches())
        self.cursor.execute(
            "SELECT COUNT(nodes.node) FROM nodes "
            "JOIN (SELECT graph, node, rev "
            "FROM nodes WHERE graph=? AND rev<=? AND branch IN ({qms}) "
            "GROUP BY graph, node) AS hirev ON "
            "nodes.graph=hirev.graph AND "
            "nodes.node=hirev.node AND "
            "nodes.rev=hirev.rev AND "
            "branch IN ({qms}) "
            "WHERE extant={true};".format(
                qms=", ".join("?" * len(branches)),
                true=self.sql_types[self.sql_flavor]['true']
            ),
            (unicode(graph), rev) + branches * 2
        )
        return int(self.cursor.fetchone()[0])

    def _node_exists(self, graph, node):
        branches = tuple(self._active_branches())
        rev = self.rev
        self.cursor.execute(
            "SELECT extant FROM nodes JOIN ("
            "SELECT graph, node, MAX(rev) AS rev FROM nodes "
            "WHERE graph=? "
            "AND node=? "
            "AND rev<=? "
            "AND branch IN ({qms})) AS hirev "
            "ON nodes.graph=hirev.graph "
            "AND nodes.node=hirev.node "
            "AND nodes.rev=hirev.rev "
            "AND branch IN ({qms});".format(
                qms=", ".join("?" * len(branches))
            ), (
                unicode(graph),
                unicode(node),
                rev
            ) + branches * 2
        )
        row = self.cursor.fetchone()
        try:
            return bool(row[0])
        except TypeError:
            return False
