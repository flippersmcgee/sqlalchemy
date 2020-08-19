# mssql/base.py
# Copyright (C) 2005-2020 the SQLAlchemy authors and contributors
# <see AUTHORS file>
#
# This module is part of SQLAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php
"""
.. dialect:: mssql
    :name: Microsoft SQL Server


.. _mssql_identity:

Auto Increment Behavior / IDENTITY Columns
------------------------------------------

SQL Server provides so-called "auto incrementing" behavior using the
``IDENTITY`` construct, which can be placed on any single integer column in a
table. SQLAlchemy considers ``IDENTITY`` within its default "autoincrement"
behavior for an integer primary key column, described at
:paramref:`_schema.Column.autoincrement`.  This means that by default,
the first
integer primary key column in a :class:`_schema.Table`
will be considered to be the
identity column - unless it is associated with a :class:`.Sequence` - and will
generate DDL as such::

    from sqlalchemy import Table, MetaData, Column, Integer

    m = MetaData()
    t = Table('t', m,
            Column('id', Integer, primary_key=True),
            Column('x', Integer))
    m.create_all(engine)

The above example will generate DDL as:

.. sourcecode:: sql

    CREATE TABLE t (
        id INTEGER NOT NULL IDENTITY(1,1),
        x INTEGER NULL,
        PRIMARY KEY (id)
    )

For the case where this default generation of ``IDENTITY`` is not desired,
specify ``False`` for the :paramref:`_schema.Column.autoincrement` flag,
on the first integer primary key column::

    m = MetaData()
    t = Table('t', m,
            Column('id', Integer, primary_key=True, autoincrement=False),
            Column('x', Integer))
    m.create_all(engine)

To add the ``IDENTITY`` keyword to a non-primary key column, specify
``True`` for the :paramref:`_schema.Column.autoincrement` flag on the desired
:class:`_schema.Column` object, and ensure that
:paramref:`_schema.Column.autoincrement`
is set to ``False`` on any integer primary key column::

    m = MetaData()
    t = Table('t', m,
            Column('id', Integer, primary_key=True, autoincrement=False),
            Column('x', Integer, autoincrement=True))
    m.create_all(engine)

.. versionchanged::  1.3   Added ``mssql_identity_start`` and
   ``mssql_identity_increment`` parameters to :class:`_schema.Column`.
   These replace
   the use of the :class:`.Sequence` object in order to specify these values.

.. deprecated:: 1.3

   The use of :class:`.Sequence` to specify IDENTITY characteristics is
   deprecated and will be removed in a future release.   Please use
   the ``mssql_identity_start`` and ``mssql_identity_increment`` parameters
   documented at :ref:`mssql_identity`.

.. versionchanged::  1.4   Removed the ability to use a :class:`.Sequence`
   object to modify IDENTITY characteristics. :class:`.Sequence` objects
   now only manipulate true T-SQL SEQUENCE types.

.. note::

    There can only be one IDENTITY column on the table.  When using
    ``autoincrement=True`` to enable the IDENTITY keyword, SQLAlchemy does not
    guard against multiple columns specifying the option simultaneously.  The
    SQL Server database will instead reject the ``CREATE TABLE`` statement.

.. note::

    An INSERT statement which attempts to provide a value for a column that is
    marked with IDENTITY will be rejected by SQL Server.   In order for the
    value to be accepted, a session-level option "SET IDENTITY_INSERT" must be
    enabled.   The SQLAlchemy SQL Server dialect will perform this operation
    automatically when using a core :class:`_expression.Insert`
    construct; if the
    execution specifies a value for the IDENTITY column, the "IDENTITY_INSERT"
    option will be enabled for the span of that statement's invocation.However,
    this scenario is not high performing and should not be relied upon for
    normal use.   If a table doesn't actually require IDENTITY behavior in its
    integer primary key column, the keyword should be disabled when creating
    the table by ensuring that ``autoincrement=False`` is set.

Controlling "Start" and "Increment"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Specific control over the "start" and "increment" values for
the ``IDENTITY`` generator are provided using the
``mssql_identity_start`` and ``mssql_identity_increment`` parameters
passed to the :class:`_schema.Column` object::

    from sqlalchemy import Table, Integer, Column

    test = Table(
        'test', metadata,
        Column(
            'id', Integer, primary_key=True, mssql_identity_start=100,
             mssql_identity_increment=10
        ),
        Column('name', String(20))
    )

The CREATE TABLE for the above :class:`_schema.Table` object would be:

.. sourcecode:: sql

   CREATE TABLE test (
     id INTEGER NOT NULL IDENTITY(100,10) PRIMARY KEY,
     name VARCHAR(20) NULL,
     )

.. versionchanged:: 1.3  The ``mssql_identity_start`` and
   ``mssql_identity_increment`` parameters are now used to affect the
   ``IDENTITY`` generator for a :class:`_schema.Column` under  SQL Server.
   Previously, the :class:`.Sequence` object was used.  As SQL Server now
   supports real sequences as a separate construct, :class:`.Sequence` will be
   functional in the normal way in a future SQLAlchemy version.

INSERT behavior
^^^^^^^^^^^^^^^^

Handling of the ``IDENTITY`` column at INSERT time involves two key
techniques. The most common is being able to fetch the "last inserted value"
for a given ``IDENTITY`` column, a process which SQLAlchemy performs
implicitly in many cases, most importantly within the ORM.

The process for fetching this value has several variants:

* In the vast majority of cases, RETURNING is used in conjunction with INSERT
  statements on SQL Server in order to get newly generated primary key values:

  .. sourcecode:: sql

    INSERT INTO t (x) OUTPUT inserted.id VALUES (?)

* When RETURNING is not available or has been disabled via
  ``implicit_returning=False``, either the ``scope_identity()`` function or
  the ``@@identity`` variable is used; behavior varies by backend:

  * when using PyODBC, the phrase ``; select scope_identity()`` will be
    appended to the end of the INSERT statement; a second result set will be
    fetched in order to receive the value.  Given a table as::

        t = Table('t', m, Column('id', Integer, primary_key=True),
                Column('x', Integer),
                implicit_returning=False)

    an INSERT will look like:

    .. sourcecode:: sql

        INSERT INTO t (x) VALUES (?); select scope_identity()

  * Other dialects such as pymssql will call upon
    ``SELECT scope_identity() AS lastrowid`` subsequent to an INSERT
    statement. If the flag ``use_scope_identity=False`` is passed to
    :func:`_sa.create_engine`,
    the statement ``SELECT @@identity AS lastrowid``
    is used instead.

A table that contains an ``IDENTITY`` column will prohibit an INSERT statement
that refers to the identity column explicitly.  The SQLAlchemy dialect will
detect when an INSERT construct, created using a core
:func:`_expression.insert`
construct (not a plain string SQL), refers to the identity column, and
in this case will emit ``SET IDENTITY_INSERT ON`` prior to the insert
statement proceeding, and ``SET IDENTITY_INSERT OFF`` subsequent to the
execution.  Given this example::

    m = MetaData()
    t = Table('t', m, Column('id', Integer, primary_key=True),
                    Column('x', Integer))
    m.create_all(engine)

    with engine.begin() as conn:
        conn.execute(t.insert(), {'id': 1, 'x':1}, {'id':2, 'x':2})

The above column will be created with IDENTITY, however the INSERT statement
we emit is specifying explicit values.  In the echo output we can see
how SQLAlchemy handles this:

.. sourcecode:: sql

    CREATE TABLE t (
        id INTEGER NOT NULL IDENTITY(1,1),
        x INTEGER NULL,
        PRIMARY KEY (id)
    )

    COMMIT
    SET IDENTITY_INSERT t ON
    INSERT INTO t (id, x) VALUES (?, ?)
    ((1, 1), (2, 2))
    SET IDENTITY_INSERT t OFF
    COMMIT



This
is an auxiliary use case suitable for testing and bulk insert scenarios.

SEQUENCE support
----------------

The :class:`.Sequence` object now creates "real" sequences, i.e.,
``CREATE SEQUENCE``. To provide compatibility with other dialects,
:class:`.Sequence` defaults to a data type of Integer and a start value of 1,
even though the T-SQL defaults are BIGINT and -9223372036854775808,
respectively.

.. versionadded:: 1.4.0

MAX on VARCHAR / NVARCHAR
-------------------------

SQL Server supports the special string "MAX" within the
:class:`_types.VARCHAR` and :class:`_types.NVARCHAR` datatypes,
to indicate "maximum length possible".   The dialect currently handles this as
a length of "None" in the base type, rather than supplying a
dialect-specific version of these types, so that a base type
specified such as ``VARCHAR(None)`` can assume "unlengthed" behavior on
more than one backend without using dialect-specific types.

To build a SQL Server VARCHAR or NVARCHAR with MAX length, use None::

    my_table = Table(
        'my_table', metadata,
        Column('my_data', VARCHAR(None)),
        Column('my_n_data', NVARCHAR(None))
    )


Collation Support
-----------------

Character collations are supported by the base string types,
specified by the string argument "collation"::

    from sqlalchemy import VARCHAR
    Column('login', VARCHAR(32, collation='Latin1_General_CI_AS'))

When such a column is associated with a :class:`_schema.Table`, the
CREATE TABLE statement for this column will yield::

    login VARCHAR(32) COLLATE Latin1_General_CI_AS NULL

LIMIT/OFFSET Support
--------------------

MSSQL has added support for LIMIT / OFFSET as of SQL Server 2012, via the
"OFFSET n ROWS" and "FETCH NEXT n ROWS" clauses.  SQLAlchemy supports these
syntaxes automatically if SQL Server 2012 or greater is detected.

.. versionchanged:: 1.4 support added for SQL Server "OFFSET n ROWS" and
   "FETCH NEXT n ROWS" syntax.

For statements that specify only LIMIT and no OFFSET, all versions of SQL
Server support the TOP keyword.   This syntax is used for all SQL Server
versions when no OFFSET clause is present.  A statement such as::

    select([some_table]).limit(5)

will render similarly to::

    SELECT TOP 5 col1, col2.. FROM table

For versions of SQL Server prior to SQL Server 2012, a statement that uses
LIMIT and OFFSET, or just OFFSET alone, will be rendered using the
``ROW_NUMBER()`` window function.   A statement such as::

    select([some_table]).order_by(some_table.c.col3).limit(5).offset(10)

will render similarly to::

    SELECT anon_1.col1, anon_1.col2 FROM (SELECT col1, col2,
    ROW_NUMBER() OVER (ORDER BY col3) AS
    mssql_rn FROM table WHERE t.x = :x_1) AS
    anon_1 WHERE mssql_rn > :param_1 AND mssql_rn <= :param_2 + :param_1

Note that when using LIMIT and/or OFFSET, whether using the older
or newer SQL Server syntaxes, the statement must have an ORDER BY as well,
else a :class:`.CompileError` is raised.

.. _mssql_isolation_level:

Transaction Isolation Level
---------------------------

All SQL Server dialects support setting of transaction isolation level
both via a dialect-specific parameter
:paramref:`_sa.create_engine.isolation_level`
accepted by :func:`_sa.create_engine`,
as well as the :paramref:`.Connection.execution_options.isolation_level`
argument as passed to
:meth:`_engine.Connection.execution_options`.
This feature works by issuing the
command ``SET TRANSACTION ISOLATION LEVEL <level>`` for
each new connection.

To set isolation level using :func:`_sa.create_engine`::

    engine = create_engine(
        "mssql+pyodbc://scott:tiger@ms_2008",
        isolation_level="REPEATABLE READ"
    )

To set using per-connection execution options::

    connection = engine.connect()
    connection = connection.execution_options(
        isolation_level="READ COMMITTED"
    )

Valid values for ``isolation_level`` include:

* ``AUTOCOMMIT`` - pyodbc / pymssql-specific
* ``READ COMMITTED``
* ``READ UNCOMMITTED``
* ``REPEATABLE READ``
* ``SERIALIZABLE``
* ``SNAPSHOT`` - specific to SQL Server

.. versionadded:: 1.2 added AUTOCOMMIT isolation level setting

.. seealso::

    :ref:`dbapi_autocommit`

Nullability
-----------
MSSQL has support for three levels of column nullability. The default
nullability allows nulls and is explicit in the CREATE TABLE
construct::

    name VARCHAR(20) NULL

If ``nullable=None`` is specified then no specification is made. In
other words the database's configured default is used. This will
render::

    name VARCHAR(20)

If ``nullable`` is ``True`` or ``False`` then the column will be
``NULL`` or ``NOT NULL`` respectively.

Date / Time Handling
--------------------
DATE and TIME are supported.   Bind parameters are converted
to datetime.datetime() objects as required by most MSSQL drivers,
and results are processed from strings if needed.
The DATE and TIME types are not available for MSSQL 2005 and
previous - if a server version below 2008 is detected, DDL
for these types will be issued as DATETIME.

.. _mssql_large_type_deprecation:

Large Text/Binary Type Deprecation
----------------------------------

Per
`SQL Server 2012/2014 Documentation <http://technet.microsoft.com/en-us/library/ms187993.aspx>`_,
the ``NTEXT``, ``TEXT`` and ``IMAGE`` datatypes are to be removed from SQL
Server in a future release.   SQLAlchemy normally relates these types to the
:class:`.UnicodeText`, :class:`_expression.TextClause` and
:class:`.LargeBinary` datatypes.

In order to accommodate this change, a new flag ``deprecate_large_types``
is added to the dialect, which will be automatically set based on detection
of the server version in use, if not otherwise set by the user.  The
behavior of this flag is as follows:

* When this flag is ``True``, the :class:`.UnicodeText`,
  :class:`_expression.TextClause` and
  :class:`.LargeBinary` datatypes, when used to render DDL, will render the
  types ``NVARCHAR(max)``, ``VARCHAR(max)``, and ``VARBINARY(max)``,
  respectively.  This is a new behavior as of the addition of this flag.

* When this flag is ``False``, the :class:`.UnicodeText`,
  :class:`_expression.TextClause` and
  :class:`.LargeBinary` datatypes, when used to render DDL, will render the
  types ``NTEXT``, ``TEXT``, and ``IMAGE``,
  respectively.  This is the long-standing behavior of these types.

* The flag begins with the value ``None``, before a database connection is
  established.   If the dialect is used to render DDL without the flag being
  set, it is interpreted the same as ``False``.

* On first connection, the dialect detects if SQL Server version 2012 or
  greater is in use; if the flag is still at ``None``, it sets it to ``True``
  or ``False`` based on whether 2012 or greater is detected.

* The flag can be set to either ``True`` or ``False`` when the dialect
  is created, typically via :func:`_sa.create_engine`::

        eng = create_engine("mssql+pymssql://user:pass@host/db",
                        deprecate_large_types=True)

* Complete control over whether the "old" or "new" types are rendered is
  available in all SQLAlchemy versions by using the UPPERCASE type objects
  instead: :class:`_types.NVARCHAR`, :class:`_types.VARCHAR`,
  :class:`_types.VARBINARY`, :class:`_types.TEXT`, :class:`_mssql.NTEXT`,
  :class:`_mssql.IMAGE`
  will always remain fixed and always output exactly that
  type.

.. versionadded:: 1.0.0

.. _multipart_schema_names:

Multipart Schema Names
----------------------

SQL Server schemas sometimes require multiple parts to their "schema"
qualifier, that is, including the database name and owner name as separate
tokens, such as ``mydatabase.dbo.some_table``. These multipart names can be set
at once using the :paramref:`_schema.Table.schema` argument of
:class:`_schema.Table`::

    Table(
        "some_table", metadata,
        Column("q", String(50)),
        schema="mydatabase.dbo"
    )

When performing operations such as table or component reflection, a schema
argument that contains a dot will be split into separate
"database" and "owner"  components in order to correctly query the SQL
Server information schema tables, as these two values are stored separately.
Additionally, when rendering the schema name for DDL or SQL, the two
components will be quoted separately for case sensitive names and other
special characters.   Given an argument as below::

    Table(
        "some_table", metadata,
        Column("q", String(50)),
        schema="MyDataBase.dbo"
    )

The above schema would be rendered as ``[MyDataBase].dbo``, and also in
reflection, would be reflected using "dbo" as the owner and "MyDataBase"
as the database name.

To control how the schema name is broken into database / owner,
specify brackets (which in SQL Server are quoting characters) in the name.
Below, the "owner" will be considered as ``MyDataBase.dbo`` and the
"database" will be None::

    Table(
        "some_table", metadata,
        Column("q", String(50)),
        schema="[MyDataBase.dbo]"
    )

To individually specify both database and owner name with special characters
or embedded dots, use two sets of brackets::

    Table(
        "some_table", metadata,
        Column("q", String(50)),
        schema="[MyDataBase.Period].[MyOwner.Dot]"
    )


.. versionchanged:: 1.2 the SQL Server dialect now treats brackets as
   identifier delimeters splitting the schema into separate database
   and owner tokens, to allow dots within either name itself.

.. _legacy_schema_rendering:

Legacy Schema Mode
------------------

Very old versions of the MSSQL dialect introduced the behavior such that a
schema-qualified table would be auto-aliased when used in a
SELECT statement; given a table::

    account_table = Table(
        'account', metadata,
        Column('id', Integer, primary_key=True),
        Column('info', String(100)),
        schema="customer_schema"
    )

this legacy mode of rendering would assume that "customer_schema.account"
would not be accepted by all parts of the SQL statement, as illustrated
below::

    >>> eng = create_engine("mssql+pymssql://mydsn", legacy_schema_aliasing=True)
    >>> print(account_table.select().compile(eng))
    SELECT account_1.id, account_1.info
    FROM customer_schema.account AS account_1

This mode of behavior is now off by default, as it appears to have served
no purpose; however in the case that legacy applications rely upon it,
it is available using the ``legacy_schema_aliasing`` argument to
:func:`_sa.create_engine` as illustrated above.

.. versionchanged:: 1.1 the ``legacy_schema_aliasing`` flag introduced
   in version 1.0.5 to allow disabling of legacy mode for schemas now
   defaults to False.


.. _mssql_indexes:

Clustered Index Support
-----------------------

The MSSQL dialect supports clustered indexes (and primary keys) via the
``mssql_clustered`` option.  This option is available to :class:`.Index`,
:class:`.UniqueConstraint`. and :class:`.PrimaryKeyConstraint`.

To generate a clustered index::

    Index("my_index", table.c.x, mssql_clustered=True)

which renders the index as ``CREATE CLUSTERED INDEX my_index ON table (x)``.

To generate a clustered primary key use::

    Table('my_table', metadata,
          Column('x', ...),
          Column('y', ...),
          PrimaryKeyConstraint("x", "y", mssql_clustered=True))

which will render the table, for example, as::

  CREATE TABLE my_table (x INTEGER NOT NULL, y INTEGER NOT NULL,
                         PRIMARY KEY CLUSTERED (x, y))

Similarly, we can generate a clustered unique constraint using::

    Table('my_table', metadata,
          Column('x', ...),
          Column('y', ...),
          PrimaryKeyConstraint("x"),
          UniqueConstraint("y", mssql_clustered=True),
          )

To explicitly request a non-clustered primary key (for example, when
a separate clustered index is desired), use::

    Table('my_table', metadata,
          Column('x', ...),
          Column('y', ...),
          PrimaryKeyConstraint("x", "y", mssql_clustered=False))

which will render the table, for example, as::

  CREATE TABLE my_table (x INTEGER NOT NULL, y INTEGER NOT NULL,
                         PRIMARY KEY NONCLUSTERED (x, y))

.. versionchanged:: 1.1 the ``mssql_clustered`` option now defaults
   to None, rather than False.  ``mssql_clustered=False`` now explicitly
   renders the NONCLUSTERED clause, whereas None omits the CLUSTERED
   clause entirely, allowing SQL Server defaults to take effect.


MSSQL-Specific Index Options
-----------------------------

In addition to clustering, the MSSQL dialect supports other special options
for :class:`.Index`.

INCLUDE
^^^^^^^

The ``mssql_include`` option renders INCLUDE(colname) for the given string
names::

    Index("my_index", table.c.x, mssql_include=['y'])

would render the index as ``CREATE INDEX my_index ON table (x) INCLUDE (y)``

.. _mssql_index_where:

Filtered Indexes
^^^^^^^^^^^^^^^^

The ``mssql_where`` option renders WHERE(condition) for the given string
names::

    Index("my_index", table.c.x, mssql_where=table.c.x > 10)

would render the index as ``CREATE INDEX my_index ON table (x) WHERE x > 10``.

.. versionadded:: 1.3.4

Index ordering
^^^^^^^^^^^^^^

Index ordering is available via functional expressions, such as::

    Index("my_index", table.c.x.desc())

would render the index as ``CREATE INDEX my_index ON table (x DESC)``

.. seealso::

    :ref:`schema_indexes_functional`

Compatibility Levels
--------------------
MSSQL supports the notion of setting compatibility levels at the
database level. This allows, for instance, to run a database that
is compatible with SQL2000 while running on a SQL2005 database
server. ``server_version_info`` will always return the database
server version information (in this case SQL2005) and not the
compatibility level information. Because of this, if running under
a backwards compatibility mode SQLAlchemy may attempt to use T-SQL
statements that are unable to be parsed by the database server.

Triggers
--------

SQLAlchemy by default uses OUTPUT INSERTED to get at newly
generated primary key values via IDENTITY columns or other
server side defaults.   MS-SQL does not
allow the usage of OUTPUT INSERTED on tables that have triggers.
To disable the usage of OUTPUT INSERTED on a per-table basis,
specify ``implicit_returning=False`` for each :class:`_schema.Table`
which has triggers::

    Table('mytable', metadata,
        Column('id', Integer, primary_key=True),
        # ...,
        implicit_returning=False
    )

Declarative form::

    class MyClass(Base):
        # ...
        __table_args__ = {'implicit_returning':False}


This option can also be specified engine-wide using the
``implicit_returning=False`` argument on :func:`_sa.create_engine`.

.. _mssql_rowcount_versioning:

Rowcount Support / ORM Versioning
---------------------------------

The SQL Server drivers may have limited ability to return the number
of rows updated from an UPDATE or DELETE statement.

As of this writing, the PyODBC driver is not able to return a rowcount when
OUTPUT INSERTED is used.  This impacts the SQLAlchemy ORM's versioning feature
in many cases where server-side value generators are in use in that while the
versioning operations can succeed, the ORM cannot always check that an UPDATE
or DELETE statement matched the number of rows expected, which is how it
verifies that the version identifier matched.   When this condition occurs, a
warning will be emitted but the operation will proceed.

The use of OUTPUT INSERTED can be disabled by setting the
:paramref:`_schema.Table.implicit_returning` flag to ``False`` on a particular
:class:`_schema.Table`, which in declarative looks like::

    class MyTable(Base):
        __tablename__ = 'mytable'
        id = Column(Integer, primary_key=True)
        stuff = Column(String(10))
        timestamp = Column(TIMESTAMP(), default=text('DEFAULT'))
        __mapper_args__ = {
            'version_id_col': timestamp,
            'version_id_generator': False,
        }
        __table_args__ = {
            'implicit_returning': False
        }

Enabling Snapshot Isolation
---------------------------

SQL Server has a default transaction
isolation mode that locks entire tables, and causes even mildly concurrent
applications to have long held locks and frequent deadlocks.
Enabling snapshot isolation for the database as a whole is recommended
for modern levels of concurrency support.  This is accomplished via the
following ALTER DATABASE commands executed at the SQL prompt::

    ALTER DATABASE MyDatabase SET ALLOW_SNAPSHOT_ISOLATION ON

    ALTER DATABASE MyDatabase SET READ_COMMITTED_SNAPSHOT ON

Background on SQL Server snapshot isolation is available at
http://msdn.microsoft.com/en-us/library/ms175095.aspx.

"""  # noqa

import codecs
import datetime
import operator
import re

from . import information_schema as ischema
from ... import exc
from ... import schema as sa_schema
from ... import Sequence
from ... import sql
from ... import types as sqltypes
from ... import util
from ...engine import cursor as _cursor
from ...engine import default
from ...engine import reflection
from ...sql import compiler
from ...sql import elements
from ...sql import expression
from ...sql import func
from ...sql import quoted_name
from ...sql import util as sql_util
from ...sql.type_api import to_instance
from ...types import BIGINT
from ...types import BINARY
from ...types import CHAR
from ...types import DATE
from ...types import DATETIME
from ...types import DECIMAL
from ...types import FLOAT
from ...types import INTEGER
from ...types import NCHAR
from ...types import NUMERIC
from ...types import NVARCHAR
from ...types import SMALLINT
from ...types import TEXT
from ...types import VARCHAR
from ...util import update_wrapper
from ...util.langhelpers import public_factory


# http://sqlserverbuilds.blogspot.com/
MS_2017_VERSION = (14,)
MS_2016_VERSION = (13,)
MS_2014_VERSION = (12,)
MS_2012_VERSION = (11,)
MS_2008_VERSION = (10,)
MS_2005_VERSION = (9,)
MS_2000_VERSION = (8,)

RESERVED_WORDS = set(
    [
        "add",
        "all",
        "alter",
        "and",
        "any",
        "as",
        "asc",
        "authorization",
        "backup",
        "begin",
        "between",
        "break",
        "browse",
        "bulk",
        "by",
        "cascade",
        "case",
        "check",
        "checkpoint",
        "close",
        "clustered",
        "coalesce",
        "collate",
        "column",
        "commit",
        "compute",
        "constraint",
        "contains",
        "containstable",
        "continue",
        "convert",
        "create",
        "cross",
        "current",
        "current_date",
        "current_time",
        "current_timestamp",
        "current_user",
        "cursor",
        "database",
        "dbcc",
        "deallocate",
        "declare",
        "default",
        "delete",
        "deny",
        "desc",
        "disk",
        "distinct",
        "distributed",
        "double",
        "drop",
        "dump",
        "else",
        "end",
        "errlvl",
        "escape",
        "except",
        "exec",
        "execute",
        "exists",
        "exit",
        "external",
        "fetch",
        "file",
        "fillfactor",
        "for",
        "foreign",
        "freetext",
        "freetexttable",
        "from",
        "full",
        "function",
        "goto",
        "grant",
        "group",
        "having",
        "holdlock",
        "identity",
        "identity_insert",
        "identitycol",
        "if",
        "in",
        "index",
        "inner",
        "insert",
        "intersect",
        "into",
        "is",
        "join",
        "key",
        "kill",
        "left",
        "like",
        "lineno",
        "load",
        "merge",
        "national",
        "nocheck",
        "nonclustered",
        "not",
        "null",
        "nullif",
        "of",
        "off",
        "offsets",
        "on",
        "open",
        "opendatasource",
        "openquery",
        "openrowset",
        "openxml",
        "option",
        "or",
        "order",
        "outer",
        "over",
        "percent",
        "pivot",
        "plan",
        "precision",
        "primary",
        "print",
        "proc",
        "procedure",
        "public",
        "raiserror",
        "read",
        "readtext",
        "reconfigure",
        "references",
        "replication",
        "restore",
        "restrict",
        "return",
        "revert",
        "revoke",
        "right",
        "rollback",
        "rowcount",
        "rowguidcol",
        "rule",
        "save",
        "schema",
        "securityaudit",
        "select",
        "session_user",
        "set",
        "setuser",
        "shutdown",
        "some",
        "statistics",
        "system_user",
        "table",
        "tablesample",
        "textsize",
        "then",
        "to",
        "top",
        "tran",
        "transaction",
        "trigger",
        "truncate",
        "tsequal",
        "union",
        "unique",
        "unpivot",
        "update",
        "updatetext",
        "use",
        "user",
        "values",
        "varying",
        "view",
        "waitfor",
        "when",
        "where",
        "while",
        "with",
        "writetext",
    ]
)


class REAL(sqltypes.REAL):
    __visit_name__ = "REAL"

    def __init__(self, **kw):
        # REAL is a synonym for FLOAT(24) on SQL server.
        # it is only accepted as the word "REAL" in DDL, the numeric
        # precision value is not allowed to be present
        kw.setdefault("precision", 24)
        super(REAL, self).__init__(**kw)


class TINYINT(sqltypes.Integer):
    __visit_name__ = "TINYINT"


# MSSQL DATE/TIME types have varied behavior, sometimes returning
# strings.  MSDate/TIME check for everything, and always
# filter bind parameters into datetime objects (required by pyodbc,
# not sure about other dialects).


class _MSDate(sqltypes.Date):
    def bind_processor(self, dialect):
        def process(value):
            if type(value) == datetime.date:
                return datetime.datetime(value.year, value.month, value.day)
            else:
                return value

        return process

    _reg = re.compile(r"(\d+)-(\d+)-(\d+)")

    def result_processor(self, dialect, coltype):
        def process(value):
            if isinstance(value, datetime.datetime):
                return value.date()
            elif isinstance(value, util.string_types):
                m = self._reg.match(value)
                if not m:
                    raise ValueError(
                        "could not parse %r as a date value" % (value,)
                    )
                return datetime.date(*[int(x or 0) for x in m.groups()])
            else:
                return value

        return process


class TIME(sqltypes.TIME):
    def __init__(self, precision=None, **kwargs):
        self.precision = precision
        super(TIME, self).__init__()

    __zero_date = datetime.date(1900, 1, 1)

    def bind_processor(self, dialect):
        def process(value):
            if isinstance(value, datetime.datetime):
                value = datetime.datetime.combine(
                    self.__zero_date, value.time()
                )
            elif isinstance(value, datetime.time):
                """ issue #5339
                per: https://github.com/mkleehammer/pyodbc/wiki/Tips-and-Tricks-by-Database-Platform#time-columns
                pass TIME value as string
                """  # noqa
                value = str(value)
            return value

        return process

    _reg = re.compile(r"(\d+):(\d+):(\d+)(?:\.(\d{0,6}))?")

    def result_processor(self, dialect, coltype):
        def process(value):
            if isinstance(value, datetime.datetime):
                return value.time()
            elif isinstance(value, util.string_types):
                m = self._reg.match(value)
                if not m:
                    raise ValueError(
                        "could not parse %r as a time value" % (value,)
                    )
                return datetime.time(*[int(x or 0) for x in m.groups()])
            else:
                return value

        return process


_MSTime = TIME


class _DateTimeBase(object):
    def bind_processor(self, dialect):
        def process(value):
            if type(value) == datetime.date:
                return datetime.datetime(value.year, value.month, value.day)
            else:
                return value

        return process


class _MSDateTime(_DateTimeBase, sqltypes.DateTime):
    pass


class SMALLDATETIME(_DateTimeBase, sqltypes.DateTime):
    __visit_name__ = "SMALLDATETIME"


class DATETIME2(_DateTimeBase, sqltypes.DateTime):
    __visit_name__ = "DATETIME2"

    def __init__(self, precision=None, **kw):
        super(DATETIME2, self).__init__(**kw)
        self.precision = precision


class DATETIMEOFFSET(_DateTimeBase, sqltypes.DateTime):
    __visit_name__ = "DATETIMEOFFSET"

    def __init__(self, precision=None, **kw):
        super(DATETIMEOFFSET, self).__init__(**kw)
        self.precision = precision


class _UnicodeLiteral(object):
    def literal_processor(self, dialect):
        def process(value):

            value = value.replace("'", "''")

            if dialect.identifier_preparer._double_percents:
                value = value.replace("%", "%%")

            return "N'%s'" % value

        return process


class _MSUnicode(_UnicodeLiteral, sqltypes.Unicode):
    pass


class _MSUnicodeText(_UnicodeLiteral, sqltypes.UnicodeText):
    pass


class TIMESTAMP(sqltypes._Binary):
    """Implement the SQL Server TIMESTAMP type.

    Note this is **completely different** than the SQL Standard
    TIMESTAMP type, which is not supported by SQL Server.  It
    is a read-only datatype that does not support INSERT of values.

    .. versionadded:: 1.2

    .. seealso::

        :class:`_mssql.ROWVERSION`

    """

    __visit_name__ = "TIMESTAMP"

    # expected by _Binary to be present
    length = None

    def __init__(self, convert_int=False):
        """Construct a TIMESTAMP or ROWVERSION type.

        :param convert_int: if True, binary integer values will
         be converted to integers on read.

        .. versionadded:: 1.2

        """
        self.convert_int = convert_int

    def result_processor(self, dialect, coltype):
        super_ = super(TIMESTAMP, self).result_processor(dialect, coltype)
        if self.convert_int:

            def process(value):
                value = super_(value)
                if value is not None:
                    # https://stackoverflow.com/a/30403242/34549
                    value = int(codecs.encode(value, "hex"), 16)
                return value

            return process
        else:
            return super_


class ROWVERSION(TIMESTAMP):
    """Implement the SQL Server ROWVERSION type.

    The ROWVERSION datatype is a SQL Server synonym for the TIMESTAMP
    datatype, however current SQL Server documentation suggests using
    ROWVERSION for new datatypes going forward.

    The ROWVERSION datatype does **not** reflect (e.g. introspect) from the
    database as itself; the returned datatype will be
    :class:`_mssql.TIMESTAMP`.

    This is a read-only datatype that does not support INSERT of values.

    .. versionadded:: 1.2

    .. seealso::

        :class:`_mssql.TIMESTAMP`

    """

    __visit_name__ = "ROWVERSION"


class NTEXT(sqltypes.UnicodeText):

    """MSSQL NTEXT type, for variable-length unicode text up to 2^30
    characters."""

    __visit_name__ = "NTEXT"


class VARBINARY(sqltypes.VARBINARY, sqltypes.LargeBinary):
    """The MSSQL VARBINARY type.

    This type is present to support "deprecate_large_types" mode where
    either ``VARBINARY(max)`` or IMAGE is rendered.   Otherwise, this type
    object is redundant vs. :class:`_types.VARBINARY`.

    .. versionadded:: 1.0.0

    .. seealso::

        :ref:`mssql_large_type_deprecation`



    """

    __visit_name__ = "VARBINARY"


class IMAGE(sqltypes.LargeBinary):
    __visit_name__ = "IMAGE"


class XML(sqltypes.Text):
    """MSSQL XML type.

    This is a placeholder type for reflection purposes that does not include
    any Python-side datatype support.   It also does not currently support
    additional arguments, such as "CONTENT", "DOCUMENT",
    "xml_schema_collection".

    .. versionadded:: 1.1.11

    """

    __visit_name__ = "XML"


class BIT(sqltypes.TypeEngine):
    __visit_name__ = "BIT"


class MONEY(sqltypes.TypeEngine):
    __visit_name__ = "MONEY"


class SMALLMONEY(sqltypes.TypeEngine):
    __visit_name__ = "SMALLMONEY"


class UNIQUEIDENTIFIER(sqltypes.TypeEngine):
    __visit_name__ = "UNIQUEIDENTIFIER"


class SQL_VARIANT(sqltypes.TypeEngine):
    __visit_name__ = "SQL_VARIANT"


class TryCast(sql.elements.Cast):
    """Represent a SQL Server TRY_CAST expression.

    """

    __visit_name__ = "try_cast"

    def __init__(self, *arg, **kw):
        """Create a TRY_CAST expression.

        :class:`.TryCast` is a subclass of SQLAlchemy's :class:`.Cast`
        construct, and works in the same way, except that the SQL expression
        rendered is "TRY_CAST" rather than "CAST"::

            from sqlalchemy import select
            from sqlalchemy import Numeric
            from sqlalchemy.dialects.mssql import try_cast

            stmt = select([
                try_cast(product_table.c.unit_price, Numeric(10, 4))
            ])

        The above would render::

            SELECT TRY_CAST (product_table.unit_price AS NUMERIC(10, 4))
            FROM product_table

        .. versionadded:: 1.3.7

        """
        super(TryCast, self).__init__(*arg, **kw)


try_cast = public_factory(TryCast, ".dialects.mssql.try_cast")

# old names.
MSDateTime = _MSDateTime
MSDate = _MSDate
MSReal = REAL
MSTinyInteger = TINYINT
MSTime = TIME
MSSmallDateTime = SMALLDATETIME
MSDateTime2 = DATETIME2
MSDateTimeOffset = DATETIMEOFFSET
MSText = TEXT
MSNText = NTEXT
MSString = VARCHAR
MSNVarchar = NVARCHAR
MSChar = CHAR
MSNChar = NCHAR
MSBinary = BINARY
MSVarBinary = VARBINARY
MSImage = IMAGE
MSBit = BIT
MSMoney = MONEY
MSSmallMoney = SMALLMONEY
MSUniqueIdentifier = UNIQUEIDENTIFIER
MSVariant = SQL_VARIANT

ischema_names = {
    "int": INTEGER,
    "bigint": BIGINT,
    "smallint": SMALLINT,
    "tinyint": TINYINT,
    "varchar": VARCHAR,
    "nvarchar": NVARCHAR,
    "char": CHAR,
    "nchar": NCHAR,
    "text": TEXT,
    "ntext": NTEXT,
    "decimal": DECIMAL,
    "numeric": NUMERIC,
    "float": FLOAT,
    "datetime": DATETIME,
    "datetime2": DATETIME2,
    "datetimeoffset": DATETIMEOFFSET,
    "date": DATE,
    "time": TIME,
    "smalldatetime": SMALLDATETIME,
    "binary": BINARY,
    "varbinary": VARBINARY,
    "bit": BIT,
    "real": REAL,
    "image": IMAGE,
    "xml": XML,
    "timestamp": TIMESTAMP,
    "money": MONEY,
    "smallmoney": SMALLMONEY,
    "uniqueidentifier": UNIQUEIDENTIFIER,
    "sql_variant": SQL_VARIANT,
}


class MSTypeCompiler(compiler.GenericTypeCompiler):
    def _extend(self, spec, type_, length=None):
        """Extend a string-type declaration with standard SQL
        COLLATE annotations.

        """

        if getattr(type_, "collation", None):
            collation = "COLLATE %s" % type_.collation
        else:
            collation = None

        if not length:
            length = type_.length

        if length:
            spec = spec + "(%s)" % length

        return " ".join([c for c in (spec, collation) if c is not None])

    def visit_FLOAT(self, type_, **kw):
        precision = getattr(type_, "precision", None)
        if precision is None:
            return "FLOAT"
        else:
            return "FLOAT(%(precision)s)" % {"precision": precision}

    def visit_TINYINT(self, type_, **kw):
        return "TINYINT"

    def visit_DATETIMEOFFSET(self, type_, **kw):
        if type_.precision is not None:
            return "DATETIMEOFFSET(%s)" % type_.precision
        else:
            return "DATETIMEOFFSET"

    def visit_TIME(self, type_, **kw):
        precision = getattr(type_, "precision", None)
        if precision is not None:
            return "TIME(%s)" % precision
        else:
            return "TIME"

    def visit_TIMESTAMP(self, type_, **kw):
        return "TIMESTAMP"

    def visit_ROWVERSION(self, type_, **kw):
        return "ROWVERSION"

    def visit_DATETIME2(self, type_, **kw):
        precision = getattr(type_, "precision", None)
        if precision is not None:
            return "DATETIME2(%s)" % precision
        else:
            return "DATETIME2"

    def visit_SMALLDATETIME(self, type_, **kw):
        return "SMALLDATETIME"

    def visit_unicode(self, type_, **kw):
        return self.visit_NVARCHAR(type_, **kw)

    def visit_text(self, type_, **kw):
        if self.dialect.deprecate_large_types:
            return self.visit_VARCHAR(type_, **kw)
        else:
            return self.visit_TEXT(type_, **kw)

    def visit_unicode_text(self, type_, **kw):
        if self.dialect.deprecate_large_types:
            return self.visit_NVARCHAR(type_, **kw)
        else:
            return self.visit_NTEXT(type_, **kw)

    def visit_NTEXT(self, type_, **kw):
        return self._extend("NTEXT", type_)

    def visit_TEXT(self, type_, **kw):
        return self._extend("TEXT", type_)

    def visit_VARCHAR(self, type_, **kw):
        return self._extend("VARCHAR", type_, length=type_.length or "max")

    def visit_CHAR(self, type_, **kw):
        return self._extend("CHAR", type_)

    def visit_NCHAR(self, type_, **kw):
        return self._extend("NCHAR", type_)

    def visit_NVARCHAR(self, type_, **kw):
        return self._extend("NVARCHAR", type_, length=type_.length or "max")

    def visit_date(self, type_, **kw):
        if self.dialect.server_version_info < MS_2008_VERSION:
            return self.visit_DATETIME(type_, **kw)
        else:
            return self.visit_DATE(type_, **kw)

    def visit_time(self, type_, **kw):
        if self.dialect.server_version_info < MS_2008_VERSION:
            return self.visit_DATETIME(type_, **kw)
        else:
            return self.visit_TIME(type_, **kw)

    def visit_large_binary(self, type_, **kw):
        if self.dialect.deprecate_large_types:
            return self.visit_VARBINARY(type_, **kw)
        else:
            return self.visit_IMAGE(type_, **kw)

    def visit_IMAGE(self, type_, **kw):
        return "IMAGE"

    def visit_XML(self, type_, **kw):
        return "XML"

    def visit_VARBINARY(self, type_, **kw):
        return self._extend("VARBINARY", type_, length=type_.length or "max")

    def visit_boolean(self, type_, **kw):
        return self.visit_BIT(type_)

    def visit_BIT(self, type_, **kw):
        return "BIT"

    def visit_MONEY(self, type_, **kw):
        return "MONEY"

    def visit_SMALLMONEY(self, type_, **kw):
        return "SMALLMONEY"

    def visit_UNIQUEIDENTIFIER(self, type_, **kw):
        return "UNIQUEIDENTIFIER"

    def visit_SQL_VARIANT(self, type_, **kw):
        return "SQL_VARIANT"


class MSExecutionContext(default.DefaultExecutionContext):
    _enable_identity_insert = False
    _select_lastrowid = False
    _lastrowid = None
    _rowcount = None
    _result_strategy = None

    def _opt_encode(self, statement):
        if not self.dialect.supports_unicode_statements:
            return self.dialect._encoder(statement)[0]
        else:
            return statement

    def pre_exec(self):
        """Activate IDENTITY_INSERT if needed."""

        if self.isinsert:
            tbl = self.compiled.statement.table
            id_column = tbl._autoincrement_column
            insert_has_identity = (id_column is not None) and (
                not isinstance(id_column.default, Sequence)
            )

            if insert_has_identity:
                compile_state = self.compiled.compile_state
                self._enable_identity_insert = (
                    id_column.key in self.compiled_parameters[0]
                ) or (
                    compile_state._dict_parameters
                    and (
                        id_column.key in compile_state._dict_parameters
                        or id_column in compile_state._dict_parameters
                    )
                )

            else:
                self._enable_identity_insert = False

            self._select_lastrowid = (
                not self.compiled.inline
                and insert_has_identity
                and not self.compiled.returning
                and not self._enable_identity_insert
                and not self.executemany
            )

            if self._enable_identity_insert:
                self.root_connection._cursor_execute(
                    self.cursor,
                    self._opt_encode(
                        "SET IDENTITY_INSERT %s ON"
                        % self.dialect.identifier_preparer.format_table(tbl)
                    ),
                    (),
                    self,
                )

    def post_exec(self):
        """Disable IDENTITY_INSERT if enabled."""

        conn = self.root_connection

        if self.isinsert or self.isupdate or self.isdelete:
            self._rowcount = self.cursor.rowcount

        if self._select_lastrowid:
            if self.dialect.use_scope_identity:
                conn._cursor_execute(
                    self.cursor,
                    "SELECT scope_identity() AS lastrowid",
                    (),
                    self,
                )
            else:
                conn._cursor_execute(
                    self.cursor, "SELECT @@identity AS lastrowid", (), self
                )
            # fetchall() ensures the cursor is consumed without closing it
            row = self.cursor.fetchall()[0]
            self._lastrowid = int(row[0])

        elif (
            self.isinsert or self.isupdate or self.isdelete
        ) and self.compiled.returning:
            self.cursor_fetch_strategy = _cursor.FullyBufferedCursorFetchStrategy(  # noqa
                self.cursor, self.cursor.description, self.cursor.fetchall()
            )

        if self._enable_identity_insert:
            conn._cursor_execute(
                self.cursor,
                self._opt_encode(
                    "SET IDENTITY_INSERT %s OFF"
                    % self.dialect.identifier_preparer.format_table(
                        self.compiled.statement.table
                    )
                ),
                (),
                self,
            )

    def get_lastrowid(self):
        return self._lastrowid

    @property
    def rowcount(self):
        if self._rowcount is not None:
            return self._rowcount
        else:
            return self.cursor.rowcount

    def handle_dbapi_exception(self, e):
        if self._enable_identity_insert:
            try:
                self.cursor.execute(
                    self._opt_encode(
                        "SET IDENTITY_INSERT %s OFF"
                        % self.dialect.identifier_preparer.format_table(
                            self.compiled.statement.table
                        )
                    )
                )
            except Exception:
                pass

    def get_result_cursor_strategy(self, result):
        if self._result_strategy:
            return self._result_strategy
        else:
            return super(MSExecutionContext, self).get_result_cursor_strategy(
                result
            )

    def fire_sequence(self, seq, type_):
        return self._execute_scalar(
            (
                "SELECT NEXT VALUE FOR %s"
                % self.dialect.identifier_preparer.format_sequence(seq)
            ),
            type_,
        )


class MSSQLCompiler(compiler.SQLCompiler):
    returning_precedes_values = True

    extract_map = util.update_copy(
        compiler.SQLCompiler.extract_map,
        {
            "doy": "dayofyear",
            "dow": "weekday",
            "milliseconds": "millisecond",
            "microseconds": "microsecond",
        },
    )

    def __init__(self, *args, **kwargs):
        self.tablealiases = {}
        super(MSSQLCompiler, self).__init__(*args, **kwargs)

    def _with_legacy_schema_aliasing(fn):
        def decorate(self, *arg, **kw):
            if self.dialect.legacy_schema_aliasing:
                return fn(self, *arg, **kw)
            else:
                super_ = getattr(super(MSSQLCompiler, self), fn.__name__)
                return super_(*arg, **kw)

        return decorate

    def visit_now_func(self, fn, **kw):
        return "CURRENT_TIMESTAMP"

    def visit_current_date_func(self, fn, **kw):
        return "GETDATE()"

    def visit_length_func(self, fn, **kw):
        return "LEN%s" % self.function_argspec(fn, **kw)

    def visit_char_length_func(self, fn, **kw):
        return "LEN%s" % self.function_argspec(fn, **kw)

    def visit_concat_op_binary(self, binary, operator, **kw):
        return "%s + %s" % (
            self.process(binary.left, **kw),
            self.process(binary.right, **kw),
        )

    def visit_true(self, expr, **kw):
        return "1"

    def visit_false(self, expr, **kw):
        return "0"

    def visit_match_op_binary(self, binary, operator, **kw):
        return "CONTAINS (%s, %s)" % (
            self.process(binary.left, **kw),
            self.process(binary.right, **kw),
        )

    def get_select_precolumns(self, select, **kw):
        """ MS-SQL puts TOP, it's version of LIMIT here """

        s = super(MSSQLCompiler, self).get_select_precolumns(select, **kw)

        if select._simple_int_limit and (
            select._offset_clause is None
            or (select._simple_int_offset and select._offset == 0)
        ):
            # ODBC drivers and possibly others
            # don't support bind params in the SELECT clause on SQL Server.
            # so have to use literal here.
            kw["literal_execute"] = True
            s += "TOP %s " % self.process(select._limit_clause, **kw)

        return s

    def get_from_hint_text(self, table, text):
        return text

    def get_crud_hint_text(self, table, text):
        return text

    def limit_clause(self, select, **kw):
        """ MSSQL 2012 supports OFFSET/FETCH operators
            Use it instead subquery with row_number

        """

        if (
            not self.dialect._supports_offset_fetch
            or (select._simple_int_limit or select._limit_clause is None)
            and (select._offset_clause is None or select._simple_int_offset)
            and not select._offset
        ):
            return ""
        # OFFSET are FETCH are options of the ORDER BY clause
        if not select._order_by_clause.clauses:
            raise exc.CompileError(
                "MSSQL requires an order_by when "
                "using an OFFSET or a non-simple "
                "LIMIT clause"
            )

        text = ""

        if select._offset_clause is not None:
            offset_str = self.process(select._offset_clause, **kw)
        else:
            offset_str = "0"
        text += "\n OFFSET %s ROWS" % offset_str

        if select._limit_clause is not None:
            text += "\n FETCH NEXT %s ROWS ONLY " % self.process(
                select._limit_clause, **kw
            )
        return text

    def visit_try_cast(self, element, **kw):
        return "TRY_CAST (%s AS %s)" % (
            self.process(element.clause, **kw),
            self.process(element.typeclause, **kw),
        )

    def translate_select_structure(self, select_stmt, **kwargs):
        """Look for ``LIMIT`` and OFFSET in a select statement, and if
        so tries to wrap it in a subquery with ``row_number()`` criterion.
        MSSQL 2012 and above are excluded

        """
        select = select_stmt

        if (
            not self.dialect._supports_offset_fetch
            and (
                (
                    not select._simple_int_limit
                    and select._limit_clause is not None
                )
                or (
                    select._offset_clause is not None
                    and not select._simple_int_offset
                    or select._offset
                )
            )
            and not getattr(select, "_mssql_visit", None)
        ):

            # to use ROW_NUMBER(), an ORDER BY is required.
            if not select._order_by_clause.clauses:
                raise exc.CompileError(
                    "MSSQL requires an order_by when "
                    "using an OFFSET or a non-simple "
                    "LIMIT clause"
                )

            _order_by_clauses = [
                sql_util.unwrap_label_reference(elem)
                for elem in select._order_by_clause.clauses
            ]

            limit_clause = select._limit_clause
            offset_clause = select._offset_clause

            select = select._generate()
            select._mssql_visit = True
            select = (
                select.add_columns(
                    sql.func.ROW_NUMBER()
                    .over(order_by=_order_by_clauses)
                    .label("mssql_rn")
                )
                .order_by(None)
                .alias()
            )

            mssql_rn = sql.column("mssql_rn")
            limitselect = sql.select(
                [c for c in select.c if c.key != "mssql_rn"]
            )
            if offset_clause is not None:
                limitselect = limitselect.where(mssql_rn > offset_clause)
                if limit_clause is not None:
                    limitselect = limitselect.where(
                        mssql_rn <= (limit_clause + offset_clause)
                    )
            else:
                limitselect = limitselect.where(mssql_rn <= (limit_clause))
            return limitselect
        else:
            return select

    @_with_legacy_schema_aliasing
    def visit_table(self, table, mssql_aliased=False, iscrud=False, **kwargs):
        if mssql_aliased is table or iscrud:
            return super(MSSQLCompiler, self).visit_table(table, **kwargs)

        # alias schema-qualified tables
        alias = self._schema_aliased_table(table)
        if alias is not None:
            return self.process(alias, mssql_aliased=table, **kwargs)
        else:
            return super(MSSQLCompiler, self).visit_table(table, **kwargs)

    @_with_legacy_schema_aliasing
    def visit_alias(self, alias, **kw):
        # translate for schema-qualified table aliases
        kw["mssql_aliased"] = alias.element
        return super(MSSQLCompiler, self).visit_alias(alias, **kw)

    @_with_legacy_schema_aliasing
    def visit_column(self, column, add_to_result_map=None, **kw):
        if (
            column.table is not None
            and (not self.isupdate and not self.isdelete)
            or self.is_subquery()
        ):
            # translate for schema-qualified table aliases
            t = self._schema_aliased_table(column.table)
            if t is not None:
                converted = elements._corresponding_column_or_error(t, column)
                if add_to_result_map is not None:
                    add_to_result_map(
                        column.name,
                        column.name,
                        (column, column.name, column.key),
                        column.type,
                    )

                return super(MSSQLCompiler, self).visit_column(converted, **kw)

        return super(MSSQLCompiler, self).visit_column(
            column, add_to_result_map=add_to_result_map, **kw
        )

    def _schema_aliased_table(self, table):
        if getattr(table, "schema", None) is not None:
            if table not in self.tablealiases:
                self.tablealiases[table] = table.alias()
            return self.tablealiases[table]
        else:
            return None

    def visit_extract(self, extract, **kw):
        field = self.extract_map.get(extract.field, extract.field)
        return "DATEPART(%s, %s)" % (field, self.process(extract.expr, **kw))

    def visit_savepoint(self, savepoint_stmt):
        return "SAVE TRANSACTION %s" % self.preparer.format_savepoint(
            savepoint_stmt
        )

    def visit_rollback_to_savepoint(self, savepoint_stmt):
        return "ROLLBACK TRANSACTION %s" % self.preparer.format_savepoint(
            savepoint_stmt
        )

    def visit_binary(self, binary, **kwargs):
        """Move bind parameters to the right-hand side of an operator, where
        possible.

        """
        if (
            isinstance(binary.left, expression.BindParameter)
            and binary.operator == operator.eq
            and not isinstance(binary.right, expression.BindParameter)
        ):
            return self.process(
                expression.BinaryExpression(
                    binary.right, binary.left, binary.operator
                ),
                **kwargs
            )
        return super(MSSQLCompiler, self).visit_binary(binary, **kwargs)

    def returning_clause(self, stmt, returning_cols):
        # SQL server returning clause requires that the columns refer to
        # the virtual table names "inserted" or "deleted".   Here, we make
        # a simple alias of our table with that name, and then adapt the
        # columns we have from the list of RETURNING columns to that new name
        # so that they render as "inserted.<colname>" / "deleted.<colname>".

        if self.isinsert or self.isupdate:
            target = stmt.table.alias("inserted")
        else:
            target = stmt.table.alias("deleted")

        adapter = sql_util.ClauseAdapter(target)

        # adapter.traverse() takes a column from our target table and returns
        # the one that is linked to the "inserted" / "deleted" tables.  So  in
        # order to retrieve these values back from the result  (e.g. like
        # row[column]), tell the compiler to also add the original unadapted
        # column to the result map.   Before #4877, these were  (unknowingly)
        # falling back using string name matching in the result set which
        # necessarily used an expensive KeyError in order to match.

        columns = [
            self._label_select_column(
                None,
                adapter.traverse(c),
                True,
                False,
                {"result_map_targets": (c,)},
            )
            for c in expression._select_iterables(returning_cols)
        ]

        return "OUTPUT " + ", ".join(columns)

    def get_cte_preamble(self, recursive):
        # SQL Server finds it too inconvenient to accept
        # an entirely optional, SQL standard specified,
        # "RECURSIVE" word with their "WITH",
        # so here we go
        return "WITH"

    def label_select_column(self, select, column, asfrom):
        if isinstance(column, expression.Function):
            return column.label(None)
        else:
            return super(MSSQLCompiler, self).label_select_column(
                select, column, asfrom
            )

    def for_update_clause(self, select, **kw):
        # "FOR UPDATE" is only allowed on "DECLARE CURSOR" which
        # SQLAlchemy doesn't use
        return ""

    def order_by_clause(self, select, **kw):
        # MSSQL only allows ORDER BY in subqueries if there is a LIMIT
        if (
            self.is_subquery()
            and not select._limit
            and (not select._offset or not self.dialect._supports_offset_fetch)
        ):
            # avoid processing the order by clause if we won't end up
            # using it, because we don't want all the bind params tacked
            # onto the positional list if that is what the dbapi requires
            return ""

        order_by = self.process(select._order_by_clause, **kw)

        if order_by:
            return " ORDER BY " + order_by
        else:
            return ""

    def update_from_clause(
        self, update_stmt, from_table, extra_froms, from_hints, **kw
    ):
        """Render the UPDATE..FROM clause specific to MSSQL.

        In MSSQL, if the UPDATE statement involves an alias of the table to
        be updated, then the table itself must be added to the FROM list as
        well. Otherwise, it is optional. Here, we add it regardless.

        """
        return "FROM " + ", ".join(
            t._compiler_dispatch(self, asfrom=True, fromhints=from_hints, **kw)
            for t in [from_table] + extra_froms
        )

    def delete_table_clause(self, delete_stmt, from_table, extra_froms):
        """If we have extra froms make sure we render any alias as hint."""
        ashint = False
        if extra_froms:
            ashint = True
        return from_table._compiler_dispatch(
            self, asfrom=True, iscrud=True, ashint=ashint
        )

    def delete_extra_from_clause(
        self, delete_stmt, from_table, extra_froms, from_hints, **kw
    ):
        """Render the DELETE .. FROM clause specific to MSSQL.

        Yes, it has the FROM keyword twice.

        """
        return "FROM " + ", ".join(
            t._compiler_dispatch(self, asfrom=True, fromhints=from_hints, **kw)
            for t in [from_table] + extra_froms
        )

    def visit_empty_set_expr(self, type_):
        return "SELECT 1 WHERE 1!=1"

    def visit_is_distinct_from_binary(self, binary, operator, **kw):
        return "NOT EXISTS (SELECT %s INTERSECT SELECT %s)" % (
            self.process(binary.left),
            self.process(binary.right),
        )

    def visit_isnot_distinct_from_binary(self, binary, operator, **kw):
        return "EXISTS (SELECT %s INTERSECT SELECT %s)" % (
            self.process(binary.left),
            self.process(binary.right),
        )

    def visit_sequence(self, seq, **kw):
        return "NEXT VALUE FOR %s" % self.preparer.format_sequence(seq)


class MSSQLStrictCompiler(MSSQLCompiler):

    """A subclass of MSSQLCompiler which disables the usage of bind
    parameters where not allowed natively by MS-SQL.

    A dialect may use this compiler on a platform where native
    binds are used.

    """

    ansi_bind_rules = True

    def visit_in_op_binary(self, binary, operator, **kw):
        kw["literal_execute"] = True
        return "%s IN %s" % (
            self.process(binary.left, **kw),
            self.process(binary.right, **kw),
        )

    def visit_notin_op_binary(self, binary, operator, **kw):
        kw["literal_execute"] = True
        return "%s NOT IN %s" % (
            self.process(binary.left, **kw),
            self.process(binary.right, **kw),
        )

    def render_literal_value(self, value, type_):
        """
        For date and datetime values, convert to a string
        format acceptable to MSSQL. That seems to be the
        so-called ODBC canonical date format which looks
        like this:

            yyyy-mm-dd hh:mi:ss.mmm(24h)

        For other data types, call the base class implementation.
        """
        # datetime and date are both subclasses of datetime.date
        if issubclass(type(value), datetime.date):
            # SQL Server wants single quotes around the date string.
            return "'" + str(value) + "'"
        else:
            return super(MSSQLStrictCompiler, self).render_literal_value(
                value, type_
            )


class MSDDLCompiler(compiler.DDLCompiler):
    def get_column_specification(self, column, **kwargs):
        colspec = self.preparer.format_column(column)

        # type is not accepted in a computed column
        if column.computed is not None:
            colspec += " " + self.process(column.computed)
        else:
            colspec += " " + self.dialect.type_compiler.process(
                column.type, type_expression=column
            )

        if column.nullable is not None:
            if (
                not column.nullable
                or column.primary_key
                or isinstance(column.default, sa_schema.Sequence)
                or column.autoincrement is True
            ):
                colspec += " NOT NULL"
            elif column.computed is None:
                # don't specify "NULL" for computed columns
                colspec += " NULL"

        if column.table is None:
            raise exc.CompileError(
                "mssql requires Table-bound columns "
                "in order to generate DDL"
            )

        if (
            column is column.table._autoincrement_column
            or column.autoincrement is True
        ):
            if not isinstance(column.default, Sequence):
                start = column.dialect_options["mssql"]["identity_start"]
                increment = column.dialect_options["mssql"][
                    "identity_increment"
                ]
                colspec += " IDENTITY(%s,%s)" % (start, increment)
        else:
            default = self.get_column_default_string(column)
            if default is not None:
                colspec += " DEFAULT " + default

        return colspec

    def visit_create_index(self, create, include_schema=False):
        index = create.element
        self._verify_index_table(index)
        preparer = self.preparer
        text = "CREATE "
        if index.unique:
            text += "UNIQUE "

        # handle clustering option
        clustered = index.dialect_options["mssql"]["clustered"]
        if clustered is not None:
            text += "CLUSTERED " if clustered else "NONCLUSTERED "
        text += "INDEX %s ON %s (%s)" % (
            self._prepared_index_name(index, include_schema=include_schema),
            preparer.format_table(index.table),
            ", ".join(
                self.sql_compiler.process(
                    expr, include_table=False, literal_binds=True
                )
                for expr in index.expressions
            ),
        )

        whereclause = index.dialect_options["mssql"]["where"]

        if whereclause is not None:
            where_compiled = self.sql_compiler.process(
                whereclause, include_table=False, literal_binds=True
            )
            text += " WHERE " + where_compiled

        # handle other included columns
        if index.dialect_options["mssql"]["include"]:
            inclusions = [
                index.table.c[col]
                if isinstance(col, util.string_types)
                else col
                for col in index.dialect_options["mssql"]["include"]
            ]

            text += " INCLUDE (%s)" % ", ".join(
                [preparer.quote(c.name) for c in inclusions]
            )

        return text

    def visit_drop_index(self, drop):
        return "\nDROP INDEX %s ON %s" % (
            self._prepared_index_name(drop.element, include_schema=False),
            self.preparer.format_table(drop.element.table),
        )

    def visit_primary_key_constraint(self, constraint):
        if len(constraint) == 0:
            return ""
        text = ""
        if constraint.name is not None:
            text += "CONSTRAINT %s " % self.preparer.format_constraint(
                constraint
            )
        text += "PRIMARY KEY "

        clustered = constraint.dialect_options["mssql"]["clustered"]
        if clustered is not None:
            text += "CLUSTERED " if clustered else "NONCLUSTERED "
        text += "(%s)" % ", ".join(
            self.preparer.quote(c.name) for c in constraint
        )
        text += self.define_constraint_deferrability(constraint)
        return text

    def visit_unique_constraint(self, constraint):
        if len(constraint) == 0:
            return ""
        text = ""
        if constraint.name is not None:
            formatted_name = self.preparer.format_constraint(constraint)
            if formatted_name is not None:
                text += "CONSTRAINT %s " % formatted_name
        text += "UNIQUE "

        clustered = constraint.dialect_options["mssql"]["clustered"]
        if clustered is not None:
            text += "CLUSTERED " if clustered else "NONCLUSTERED "
        text += "(%s)" % ", ".join(
            self.preparer.quote(c.name) for c in constraint
        )
        text += self.define_constraint_deferrability(constraint)
        return text

    def visit_computed_column(self, generated):
        text = "AS (%s)" % self.sql_compiler.process(
            generated.sqltext, include_table=False, literal_binds=True
        )
        # explicitly check for True|False since None means server default
        if generated.persisted is True:
            text += " PERSISTED"
        return text

    def visit_create_sequence(self, create, **kw):

        if create.element.data_type is not None:
            data_type = create.element.data_type
        else:
            data_type = to_instance(self.dialect.sequence_default_column_type)

        prefix = " AS %s" % self.type_compiler.process(data_type)
        return super(MSDDLCompiler, self).visit_create_sequence(
            create, prefix=prefix, **kw
        )


class MSIdentifierPreparer(compiler.IdentifierPreparer):
    reserved_words = RESERVED_WORDS

    def __init__(self, dialect):
        super(MSIdentifierPreparer, self).__init__(
            dialect,
            initial_quote="[",
            final_quote="]",
            quote_case_sensitive_collations=False,
        )

    def _escape_identifier(self, value):
        return value.replace("]", "]]")

    def _unescape_identifier(self, value):
        return value.replace("]]", "]")

    def quote_schema(self, schema, force=None):
        """Prepare a quoted table and schema name."""

        # need to re-implement the deprecation warning entirely
        if force is not None:
            # not using the util.deprecated_params() decorator in this
            # case because of the additional function call overhead on this
            # very performance-critical spot.
            util.warn_deprecated(
                "The IdentifierPreparer.quote_schema.force parameter is "
                "deprecated and will be removed in a future release.  This "
                "flag has no effect on the behavior of the "
                "IdentifierPreparer.quote method; please refer to "
                "quoted_name().",
                version="1.3",
            )

        dbname, owner = _schema_elements(schema)
        if dbname:
            result = "%s.%s" % (self.quote(dbname), self.quote(owner))
        elif owner:
            result = self.quote(owner)
        else:
            result = ""
        return result


def _db_plus_owner_listing(fn):
    def wrap(dialect, connection, schema=None, **kw):
        dbname, owner = _owner_plus_db(dialect, schema)
        return _switch_db(
            dbname,
            connection,
            fn,
            dialect,
            connection,
            dbname,
            owner,
            schema,
            **kw
        )

    return update_wrapper(wrap, fn)


def _db_plus_owner(fn):
    def wrap(dialect, connection, tablename, schema=None, **kw):
        dbname, owner = _owner_plus_db(dialect, schema)
        return _switch_db(
            dbname,
            connection,
            fn,
            dialect,
            connection,
            tablename,
            dbname,
            owner,
            schema,
            **kw
        )

    return update_wrapper(wrap, fn)


def _switch_db(dbname, connection, fn, *arg, **kw):
    if dbname:
        current_db = connection.exec_driver_sql("select db_name()").scalar()
        if current_db != dbname:
            connection.exec_driver_sql(
                "use %s" % connection.dialect.identifier_preparer.quote(dbname)
            )
    try:
        return fn(*arg, **kw)
    finally:
        if dbname and current_db != dbname:
            connection.exec_driver_sql(
                "use %s"
                % connection.dialect.identifier_preparer.quote(current_db)
            )


def _owner_plus_db(dialect, schema):
    if not schema:
        return None, dialect.default_schema_name
    elif "." in schema:
        return _schema_elements(schema)
    else:
        return None, schema


_memoized_schema = util.LRUCache()


def _schema_elements(schema):
    if isinstance(schema, quoted_name) and schema.quote:
        return None, schema

    if schema in _memoized_schema:
        return _memoized_schema[schema]

    # tests for this function are in:
    # test/dialect/mssql/test_reflection.py ->
    #           OwnerPlusDBTest.test_owner_database_pairs
    # test/dialect/mssql/test_compiler.py -> test_force_schema_*
    # test/dialect/mssql/test_compiler.py -> test_schema_many_tokens_*
    #

    push = []
    symbol = ""
    bracket = False
    has_brackets = False
    for token in re.split(r"(\[|\]|\.)", schema):
        if not token:
            continue
        if token == "[":
            bracket = True
            has_brackets = True
        elif token == "]":
            bracket = False
        elif not bracket and token == ".":
            if has_brackets:
                push.append("[%s]" % symbol)
            else:
                push.append(symbol)
            symbol = ""
            has_brackets = False
        else:
            symbol += token
    if symbol:
        push.append(symbol)
    if len(push) > 1:
        dbname, owner = ".".join(push[0:-1]), push[-1]

        # test for internal brackets
        if re.match(r".*\].*\[.*", dbname[1:-1]):
            dbname = quoted_name(dbname, quote=False)
        else:
            dbname = dbname.lstrip("[").rstrip("]")

    elif len(push):
        dbname, owner = None, push[0]
    else:
        dbname, owner = None, None

    _memoized_schema[schema] = dbname, owner
    return dbname, owner


class MSDialect(default.DefaultDialect):
    name = "mssql"
    supports_default_values = True
    supports_empty_insert = False
    execution_ctx_cls = MSExecutionContext
    use_scope_identity = True
    max_identifier_length = 128
    schema_name = "dbo"

    implicit_returning = True
    full_returning = True

    colspecs = {
        sqltypes.DateTime: _MSDateTime,
        sqltypes.Date: _MSDate,
        sqltypes.Time: TIME,
        sqltypes.Unicode: _MSUnicode,
        sqltypes.UnicodeText: _MSUnicodeText,
    }

    engine_config_types = default.DefaultDialect.engine_config_types.union(
        {"legacy_schema_aliasing": util.asbool}
    )

    ischema_names = ischema_names

    supports_sequences = True
    # T-SQL's actual default is BIGINT
    sequence_default_column_type = INTEGER
    # T-SQL's actual default is -9223372036854775808
    default_sequence_base = 1

    supports_native_boolean = False
    non_native_boolean_check_constraint = False
    supports_unicode_binds = True
    postfetch_lastrowid = True
    _supports_offset_fetch = False
    _supports_nvarchar_max = False

    server_version_info = ()

    statement_compiler = MSSQLCompiler
    ddl_compiler = MSDDLCompiler
    type_compiler = MSTypeCompiler
    preparer = MSIdentifierPreparer

    construct_arguments = [
        (sa_schema.PrimaryKeyConstraint, {"clustered": None}),
        (sa_schema.UniqueConstraint, {"clustered": None}),
        (sa_schema.Index, {"clustered": None, "include": None, "where": None}),
        (sa_schema.Column, {"identity_start": 1, "identity_increment": 1}),
    ]

    def __init__(
        self,
        query_timeout=None,
        use_scope_identity=True,
        schema_name="dbo",
        isolation_level=None,
        deprecate_large_types=None,
        legacy_schema_aliasing=False,
        **opts
    ):
        self.query_timeout = int(query_timeout or 0)
        self.schema_name = schema_name

        self.use_scope_identity = use_scope_identity
        self.deprecate_large_types = deprecate_large_types
        self.legacy_schema_aliasing = legacy_schema_aliasing

        super(MSDialect, self).__init__(**opts)

        self.isolation_level = isolation_level

    def do_savepoint(self, connection, name):
        # give the DBAPI a push
        connection.exec_driver_sql("IF @@TRANCOUNT = 0 BEGIN TRANSACTION")
        super(MSDialect, self).do_savepoint(connection, name)

    def do_release_savepoint(self, connection, name):
        # SQL Server does not support RELEASE SAVEPOINT
        pass

    _isolation_lookup = set(
        [
            "SERIALIZABLE",
            "READ UNCOMMITTED",
            "READ COMMITTED",
            "REPEATABLE READ",
            "SNAPSHOT",
        ]
    )

    def set_isolation_level(self, connection, level):
        level = level.replace("_", " ")
        if level not in self._isolation_lookup:
            raise exc.ArgumentError(
                "Invalid value '%s' for isolation_level. "
                "Valid isolation levels for %s are %s"
                % (level, self.name, ", ".join(self._isolation_lookup))
            )
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION ISOLATION LEVEL %s" % level)
        cursor.close()
        if level == "SNAPSHOT":
            connection.commit()

    def get_isolation_level(self, connection):
        if self.server_version_info < MS_2005_VERSION:
            raise NotImplementedError(
                "Can't fetch isolation level prior to SQL Server 2005"
            )

        last_error = None

        views = ("sys.dm_exec_sessions", "sys.dm_pdw_nodes_exec_sessions")
        for view in views:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                  SELECT CASE transaction_isolation_level
                    WHEN 0 THEN NULL
                    WHEN 1 THEN 'READ UNCOMMITTED'
                    WHEN 2 THEN 'READ COMMITTED'
                    WHEN 3 THEN 'REPEATABLE READ'
                    WHEN 4 THEN 'SERIALIZABLE'
                    WHEN 5 THEN 'SNAPSHOT' END AS TRANSACTION_ISOLATION_LEVEL
                    FROM %s
                    where session_id = @@SPID
                  """
                    % view
                )
                val = cursor.fetchone()[0]
            except self.dbapi.Error as err:
                # Python3 scoping rules
                last_error = err
                continue
            else:
                return val.upper()
            finally:
                cursor.close()
        else:
            # note that the NotImplementedError is caught by
            # DefaultDialect, so the warning here is all that displays
            util.warn(
                "Could not fetch transaction isolation level, "
                "tried views: %s; final error was: %s" % (views, last_error)
            )
            raise NotImplementedError(
                "Can't fetch isolation level on this particular "
                "SQL Server version. tried views: %s; final error was: %s"
                % (views, last_error)
            )

    def initialize(self, connection):
        super(MSDialect, self).initialize(connection)
        self._setup_version_attributes()
        self._setup_supports_nvarchar_max(connection)

    def on_connect(self):
        if self.isolation_level is not None:

            def connect(conn):
                self.set_isolation_level(conn, self.isolation_level)

            return connect
        else:
            return None

    def _setup_version_attributes(self):
        if self.server_version_info[0] not in list(range(8, 17)):
            util.warn(
                "Unrecognized server version info '%s'.  Some SQL Server "
                "features may not function properly."
                % ".".join(str(x) for x in self.server_version_info)
            )

        if self.server_version_info < MS_2005_VERSION:
            self.implicit_returning = self.full_returning = False

        if self.server_version_info >= MS_2008_VERSION:
            self.supports_multivalues_insert = True
        if self.deprecate_large_types is None:
            self.deprecate_large_types = (
                self.server_version_info >= MS_2012_VERSION
            )

        self._supports_offset_fetch = (
            self.server_version_info and self.server_version_info[0] >= 11
        )

    def _setup_supports_nvarchar_max(self, connection):
        try:
            connection.scalar(
                sql.text("SELECT CAST('test max support' AS NVARCHAR(max))")
            )
        except exc.DBAPIError:
            self._supports_nvarchar_max = False
        else:
            self._supports_nvarchar_max = True

    def _get_default_schema_name(self, connection):
        if self.server_version_info < MS_2005_VERSION:
            return self.schema_name
        else:
            query = sql.text("SELECT schema_name()")
            default_schema_name = connection.scalar(query)
            if default_schema_name is not None:
                # guard against the case where the default_schema_name is being
                # fed back into a table reflection function.
                return quoted_name(default_schema_name, quote=True)
            else:
                return self.schema_name

    @_db_plus_owner
    def has_table(self, connection, tablename, dbname, owner, schema):
        tables = ischema.tables

        s = sql.select(tables.c.table_name).where(
            sql.and_(
                tables.c.table_type == "BASE TABLE",
                tables.c.table_name == tablename,
            )
        )

        if owner:
            s = s.where(tables.c.table_schema == owner)

        c = connection.execute(s)

        return c.first() is not None

    @_db_plus_owner
    def has_sequence(self, connection, sequencename, dbname, owner, schema):
        sequences = ischema.sequences

        s = sql.select(sequences.c.sequence_name).where(
            sequences.c.sequence_name == sequencename
        )

        if owner:
            s = s.where(sequences.c.sequence_schema == owner)

        c = connection.execute(s)

        return c.first() is not None

    @reflection.cache
    @_db_plus_owner_listing
    def get_sequence_names(self, connection, dbname, owner, schema, **kw):
        sequences = ischema.sequences

        s = sql.select(sequences.c.sequence_name)
        if owner:
            s = s.where(sequences.c.sequence_schema == owner)

        c = connection.execute(s)

        return [row[0] for row in c]

    @reflection.cache
    def get_schema_names(self, connection, **kw):
        s = sql.select(
            [ischema.schemata.c.schema_name],
            order_by=[ischema.schemata.c.schema_name],
        )
        return [r[0] for r in connection.execute(s)]

    @reflection.cache
    @_db_plus_owner_listing
    def get_table_names(self, connection, dbname, owner, schema, **kw):
        tables = ischema.tables
        s = (
            sql.select(tables.c.table_name)
            .where(
                sql.and_(
                    tables.c.table_schema == owner,
                    tables.c.table_type == "BASE TABLE",
                )
            )
            .order_by(tables.c.table_name)
        )
        return [r[0] for r in connection.execute(s)]

    @reflection.cache
    @_db_plus_owner_listing
    def get_view_names(self, connection, dbname, owner, schema, **kw):
        tables = ischema.tables
        s = (
            sql.select(tables.c.table_name)
            .where(
                sql.and_(
                    tables.c.table_schema == owner,
                    tables.c.table_type == "VIEW",
                )
            )
            .order_by(tables.c.table_name)
        )
        return [r[0] for r in connection.execute(s)]

    @reflection.cache
    @_db_plus_owner
    def get_indexes(self, connection, tablename, dbname, owner, schema, **kw):
        # using system catalogs, don't support index reflection
        # below MS 2005
        if self.server_version_info < MS_2005_VERSION:
            return []

        rp = connection.execution_options(future_result=True).execute(
            sql.text(
                "select ind.index_id, ind.is_unique, ind.name "
                "from sys.indexes as ind join sys.tables as tab on "
                "ind.object_id=tab.object_id "
                "join sys.schemas as sch on sch.schema_id=tab.schema_id "
                "where tab.name = :tabname "
                "and sch.name=:schname "
                "and ind.is_primary_key=0 and ind.type != 0"
            )
            .bindparams(
                sql.bindparam("tabname", tablename, ischema.CoerceUnicode()),
                sql.bindparam("schname", owner, ischema.CoerceUnicode()),
            )
            .columns(name=sqltypes.Unicode())
        )
        indexes = {}
        for row in rp.mappings():
            indexes[row["index_id"]] = {
                "name": row["name"],
                "unique": row["is_unique"] == 1,
                "column_names": [],
            }
        rp = connection.execution_options(future_result=True).execute(
            sql.text(
                "select ind_col.index_id, ind_col.object_id, col.name "
                "from sys.columns as col "
                "join sys.tables as tab on tab.object_id=col.object_id "
                "join sys.index_columns as ind_col on "
                "(ind_col.column_id=col.column_id and "
                "ind_col.object_id=tab.object_id) "
                "join sys.schemas as sch on sch.schema_id=tab.schema_id "
                "where tab.name=:tabname "
                "and sch.name=:schname"
            )
            .bindparams(
                sql.bindparam("tabname", tablename, ischema.CoerceUnicode()),
                sql.bindparam("schname", owner, ischema.CoerceUnicode()),
            )
            .columns(name=sqltypes.Unicode())
        )
        for row in rp.mappings():
            if row["index_id"] in indexes:
                indexes[row["index_id"]]["column_names"].append(row["name"])

        return list(indexes.values())

    @reflection.cache
    @_db_plus_owner
    def get_view_definition(
        self, connection, viewname, dbname, owner, schema, **kw
    ):
        rp = connection.execute(
            sql.text(
                "select definition from sys.sql_modules as mod, "
                "sys.views as views, "
                "sys.schemas as sch"
                " where "
                "mod.object_id=views.object_id and "
                "views.schema_id=sch.schema_id and "
                "views.name=:viewname and sch.name=:schname"
            ).bindparams(
                sql.bindparam("viewname", viewname, ischema.CoerceUnicode()),
                sql.bindparam("schname", owner, ischema.CoerceUnicode()),
            )
        )

        if rp:
            return rp.scalar()

    @reflection.cache
    @_db_plus_owner
    def get_columns(self, connection, tablename, dbname, owner, schema, **kw):
        # Get base columns
        columns = ischema.columns
        computed_cols = ischema.computed_columns
        if owner:
            whereclause = sql.and_(
                columns.c.table_name == tablename,
                columns.c.table_schema == owner,
            )
            table_fullname = "%s.%s" % (owner, tablename)
            full_name = columns.c.table_schema + "." + columns.c.table_name
            join_on = computed_cols.c.object_id == func.object_id(full_name)
        else:
            whereclause = columns.c.table_name == tablename
            table_fullname = tablename
            join_on = computed_cols.c.object_id == func.object_id(
                columns.c.table_name
            )

        join_on = sql.and_(
            join_on, columns.c.column_name == computed_cols.c.name
        )
        join = columns.join(computed_cols, onclause=join_on, isouter=True)

        if self._supports_nvarchar_max:
            computed_definition = computed_cols.c.definition
        else:
            # tds_version 4.2 does not support NVARCHAR(MAX)
            computed_definition = sql.cast(
                computed_cols.c.definition, NVARCHAR(4000)
            )

        s = (
            sql.select(
                columns, computed_definition, computed_cols.c.is_persisted
            )
            .where(whereclause)
            .select_from(join)
            .order_by(columns.c.ordinal_position)
        )

        c = connection.execution_options(future_result=True).execute(s)
        cols = []
        for row in c.mappings():
            name = row[columns.c.column_name]
            type_ = row[columns.c.data_type]
            nullable = row[columns.c.is_nullable] == "YES"
            charlen = row[columns.c.character_maximum_length]
            numericprec = row[columns.c.numeric_precision]
            numericscale = row[columns.c.numeric_scale]
            default = row[columns.c.column_default]
            collation = row[columns.c.collation_name]
            definition = row[computed_definition]
            is_persisted = row[computed_cols.c.is_persisted]

            coltype = self.ischema_names.get(type_, None)

            kwargs = {}
            if coltype in (
                MSString,
                MSChar,
                MSNVarchar,
                MSNChar,
                MSText,
                MSNText,
                MSBinary,
                MSVarBinary,
                sqltypes.LargeBinary,
            ):
                if charlen == -1:
                    charlen = None
                kwargs["length"] = charlen
                if collation:
                    kwargs["collation"] = collation

            if coltype is None:
                util.warn(
                    "Did not recognize type '%s' of column '%s'"
                    % (type_, name)
                )
                coltype = sqltypes.NULLTYPE
            else:
                if issubclass(coltype, sqltypes.Numeric):
                    kwargs["precision"] = numericprec

                    if not issubclass(coltype, sqltypes.Float):
                        kwargs["scale"] = numericscale

                coltype = coltype(**kwargs)
            cdict = {
                "name": name,
                "type": coltype,
                "nullable": nullable,
                "default": default,
                "autoincrement": False,
            }

            if definition is not None and is_persisted is not None:
                cdict["computed"] = {
                    "sqltext": definition,
                    "persisted": is_persisted,
                }

            cols.append(cdict)
        # autoincrement and identity
        colmap = {}
        for col in cols:
            colmap[col["name"]] = col
        # We also run an sp_columns to check for identity columns:
        cursor = connection.execute(
            sql.text(
                "sp_columns @table_name = :table_name, "
                "@table_owner = :table_owner",
            ),
            {"table_name": tablename, "table_owner": owner},
        )
        ic = None
        while True:
            row = cursor.fetchone()
            if row is None:
                break
            (col_name, type_name) = row[3], row[5]
            if type_name.endswith("identity") and col_name in colmap:
                ic = col_name
                colmap[col_name]["autoincrement"] = True
                colmap[col_name]["dialect_options"] = {
                    "mssql_identity_start": 1,
                    "mssql_identity_increment": 1,
                }
                break
        cursor.close()

        if ic is not None and self.server_version_info >= MS_2005_VERSION:
            table_fullname = "%s.%s" % (owner, tablename)
            cursor = connection.exec_driver_sql(
                "select ident_seed('%s'), ident_incr('%s')"
                % (table_fullname, table_fullname)
            )

            row = cursor.first()
            if row is not None and row[0] is not None:
                colmap[ic]["dialect_options"].update(
                    {
                        "mssql_identity_start": int(row[0]),
                        "mssql_identity_increment": int(row[1]),
                    }
                )
        return cols

    @reflection.cache
    @_db_plus_owner
    def get_pk_constraint(
        self, connection, tablename, dbname, owner, schema, **kw
    ):
        pkeys = []
        TC = ischema.constraints
        C = ischema.key_constraints.alias("C")

        # Primary key constraints
        s = sql.select(
            C.c.column_name, TC.c.constraint_type, C.c.constraint_name
        ).where(
            sql.and_(
                TC.c.constraint_name == C.c.constraint_name,
                TC.c.table_schema == C.c.table_schema,
                C.c.table_name == tablename,
                C.c.table_schema == owner,
            ),
        )
        c = connection.execution_options(future_result=True).execute(s)
        constraint_name = None
        for row in c.mappings():
            if "PRIMARY" in row[TC.c.constraint_type.name]:
                pkeys.append(row["COLUMN_NAME"])
                if constraint_name is None:
                    constraint_name = row[C.c.constraint_name.name]
        return {"constrained_columns": pkeys, "name": constraint_name}

    @reflection.cache
    @_db_plus_owner
    def get_foreign_keys(
        self, connection, tablename, dbname, owner, schema, **kw
    ):
        RR = ischema.ref_constraints
        C = ischema.key_constraints.alias("C")
        R = ischema.key_constraints.alias("R")

        # Foreign key constraints
        s = (
            sql.select(
                C.c.column_name,
                R.c.table_schema,
                R.c.table_name,
                R.c.column_name,
                RR.c.constraint_name,
                RR.c.match_option,
                RR.c.update_rule,
                RR.c.delete_rule,
            )
            .where(
                sql.and_(
                    C.c.table_name == tablename,
                    C.c.table_schema == owner,
                    RR.c.constraint_schema == C.c.table_schema,
                    C.c.constraint_name == RR.c.constraint_name,
                    R.c.constraint_name == RR.c.unique_constraint_name,
                    R.c.constraint_schema == RR.c.unique_constraint_schema,
                    C.c.ordinal_position == R.c.ordinal_position,
                )
            )
            .order_by(RR.c.constraint_name, R.c.ordinal_position)
        )

        # group rows by constraint ID, to handle multi-column FKs
        fkeys = []

        def fkey_rec():
            return {
                "name": None,
                "constrained_columns": [],
                "referred_schema": None,
                "referred_table": None,
                "referred_columns": [],
            }

        fkeys = util.defaultdict(fkey_rec)

        for r in connection.execute(s).fetchall():
            scol, rschema, rtbl, rcol, rfknm, fkmatch, fkuprule, fkdelrule = r

            rec = fkeys[rfknm]
            rec["name"] = rfknm
            if not rec["referred_table"]:
                rec["referred_table"] = rtbl
                if schema is not None or owner != rschema:
                    if dbname:
                        rschema = dbname + "." + rschema
                    rec["referred_schema"] = rschema

            local_cols, remote_cols = (
                rec["constrained_columns"],
                rec["referred_columns"],
            )

            local_cols.append(scol)
            remote_cols.append(rcol)

        return list(fkeys.values())
