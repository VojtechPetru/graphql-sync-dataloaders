import threading
from unittest import mock
from unittest.mock import Mock
from functools import partial

from graphql import (
    graphql_sync,
    GraphQLSchema,
    GraphQLObjectType,
    GraphQLField,
    GraphQLArgument,
    GraphQLString,
    GraphQLList,
)

from graphql_sync_dataloaders import DeferredExecutionContext, SyncDataLoader

graphql_sync_deferred = partial(graphql_sync, execution_context_class=DeferredExecutionContext)


def test_deferred_execution():
    NAMES = {
        "1": "Sarah",
        "2": "Lucy",
        "3": "Geoff",
        "5": "Dave",
    }

    def load_fn(keys):
        return [NAMES[key] for key in keys]

    mock_load_fn = Mock(wraps=load_fn)
    dataloader = SyncDataLoader(mock_load_fn)

    def resolve_name(_, __, key):
        return dataloader.load(key)

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "name": GraphQLField(
                    GraphQLString,
                    args={
                        "key": GraphQLArgument(GraphQLString),
                    },
                    resolve=resolve_name,
                )
            },
        )
    )

    result = graphql_sync_deferred(
        schema,
        """
        query {
            name1: name(key: "1")
            name2: name(key: "2")
        }
        """,
    )

    assert not result.errors
    assert result.data == {"name1": "Sarah", "name2": "Lucy"}
    assert mock_load_fn.call_count == 1


def test_nested_deferred_execution():
    USERS = {
        "1": {
            "name": "Laura",
            "bestFriend": "2",
        },
        "2": {
            "name": "Sarah",
            "bestFriend": None,
        },
        "3": {
            "name": "Dave",
            "bestFriend": "2",
        },
    }

    def load_fn(keys):
        return [USERS[key] for key in keys]

    mock_load_fn = Mock(wraps=load_fn)
    dataloader = SyncDataLoader(mock_load_fn)

    def resolve_user(_, __, id):
        return dataloader.load(id)

    def resolve_best_friend(user, _):
        return dataloader.load(user["bestFriend"])

    user = GraphQLObjectType(
        name="User",
        fields=lambda: {
            "name": GraphQLField(GraphQLString),
            "bestFriend": GraphQLField(user, resolve=resolve_best_friend),
        },
    )

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "user": GraphQLField(
                    user,
                    args={
                        "id": GraphQLArgument(GraphQLString),
                    },
                    resolve=resolve_user,
                )
            },
        )
    )

    result = graphql_sync_deferred(
        schema,
        """
        query {
            user1: user(id: "1") {
                name
                bestFriend {
                    name
                }
            }
            user2: user(id: "3") {
                name
                bestFriend {
                    name
                }
            }
        }
        """,
    )

    assert not result.errors
    assert result.data == {
        "user1": {
            "name": "Laura",
            "bestFriend": {
                "name": "Sarah",
            },
        },
        "user2": {
            "name": "Dave",
            "bestFriend": {
                "name": "Sarah",
            },
        },
    }
    assert mock_load_fn.call_count == 2


def test_deferred_execution_list():
    USERS = {
        "1": {
            "name": "Laura",
            "bestFriend": "2",
        },
        "2": {
            "name": "Sarah",
            "bestFriend": None,
        },
        "3": {
            "name": "Dave",
            "bestFriend": "2",
        },
    }

    def load_fn(keys):
        return [USERS[key] for key in keys]

    mock_load_fn = Mock(wraps=load_fn)
    dataloader = SyncDataLoader(mock_load_fn)

    def resolve_users(_, __):
        return [dataloader.load(id) for id in USERS]

    def resolve_best_friend(user, _):
        if user["bestFriend"]:
            return dataloader.load(user["bestFriend"])
        return None

    user = GraphQLObjectType(
        name="User",
        fields=lambda: {
            "name": GraphQLField(GraphQLString),
            "bestFriend": GraphQLField(user, resolve=resolve_best_friend),
        },
    )

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "users": GraphQLField(
                    GraphQLList(user),
                    resolve=resolve_users,
                )
            },
        )
    )

    result = graphql_sync_deferred(
        schema,
        """
        query {
            users {
                name
                bestFriend {
                    name
                }
            }
        }
        """,
    )

    if result.errors:
        original_error = result.errors[0].original_error
        if not original_error:
            raise result.errors[0]
        raise original_error
    assert not result.errors
    assert result.data == {
        "users": [
            {
                "name": "Laura",
                "bestFriend": {
                    "name": "Sarah",
                },
            },
            {
                "name": "Sarah",
                "bestFriend": None,
            },
            {
                "name": "Dave",
                "bestFriend": {
                    "name": "Sarah",
                },
            },
        ],
    }
    assert mock_load_fn.call_count == 1


def test_deferred_execution_errors():
    USERS = {
        "1": {
            "name": "Laura",
            "bestFriend": "2",
        },
        "2": ValueError("Sarah has left"),
        "3": {
            "name": "Dave",
            "bestFriend": "2",
        },
    }

    def load_fn(keys):
        return [USERS[key] for key in keys]

    mock_load_fn = Mock(wraps=load_fn)
    dataloader = SyncDataLoader(mock_load_fn)

    def resolve_users(_, __):
        return [dataloader.load(id) for id in USERS]

    def resolve_best_friend(user, _):
        if user["bestFriend"]:
            return dataloader.load(user["bestFriend"])
        return None

    user = GraphQLObjectType(
        name="User",
        fields=lambda: {
            "name": GraphQLField(GraphQLString),
            "bestFriend": GraphQLField(user, resolve=resolve_best_friend),
        },
    )

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "users": GraphQLField(
                    GraphQLList(user),
                    resolve=resolve_users,
                )
            },
        )
    )

    result = graphql_sync_deferred(
        schema,
        """
        query {
            users {
                name
                bestFriend {
                    name
                }
            }
        }
        """,
    )

    assert result.errors == [
        {"message": "Sarah has left", "locations": [(3, 13)], "path": ["users", 1]},
        {
            "message": "Sarah has left",
            "locations": [(5, 17)],
            "path": ["users", 0, "bestFriend"],
        },
        {
            "message": "Sarah has left",
            "locations": [(5, 17)],
            "path": ["users", 2, "bestFriend"],
        },
    ]
    assert result.data == {
        "users": [
            {
                "name": "Laura",
                "bestFriend": None,
            },
            None,
            {
                "name": "Dave",
                "bestFriend": None,
            },
        ],
    }
    assert mock_load_fn.call_count == 1


def test_result_field_ordering():
    NAMES = {
        "1": "Sarah",
        "2": "Lucy",
        "3": "Geoff",
        "5": "Dave",
    }

    def load_fn(keys):
        return [NAMES[key] for key in keys]

    mock_load_fn = Mock(wraps=load_fn)
    dataloader = SyncDataLoader(mock_load_fn)

    def resolve_name(_, __, key):
        return dataloader.load(key)

    def resolve_hello(_, __, name):
        return f"hello {name}"

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "name": GraphQLField(
                    GraphQLString,
                    args={
                        "key": GraphQLArgument(GraphQLString),
                    },
                    resolve=resolve_name,
                ),
                "hello": GraphQLField(
                    GraphQLString,
                    args={
                        "name": GraphQLArgument(GraphQLString),
                    },
                    resolve=resolve_hello,
                ),
            },
        )
    )

    result = graphql_sync_deferred(
        schema,
        """
        query {
            name1: name(key: "1")
            hello1: hello(name: "grace")
            name2: name(key: "2")
            hello2: hello(name: "lucy")
        }
        """,
    )

    assert not result.errors
    assert result.data
    assert result.data == {
        "name1": "Sarah",
        "hello1": "hello grace",
        "name2": "Lucy",
        "hello2": "hello lucy",
    }
    keys = list(result.data.keys())
    assert keys == ["name1", "hello1", "name2", "hello2"]
    assert mock_load_fn.call_count == 1


def test_chaining_dataloader():
    USERS = {
        "1": {
            "name": "Sarah",
            "best_friend": "2",
        },
        "2": {
            "name": "Lucy",
            "best_friend": "3",
        },
        "3": {
            "name": "Geoff",
        },
        "5": {
            "name": "Dave",
        },
    }

    def load_fn(keys):
        return [USERS[key] if key in USERS else None for key in keys]

    mock_load_fn = Mock(wraps=load_fn)
    dataloader = SyncDataLoader(mock_load_fn)

    def resolve_name(_, __, userId):
        return dataloader.load(userId).then(lambda user: user["name"])

    def resolve_best_friend_name(_, __, userId):
        return (
            dataloader.load(userId)
            .then(lambda user: dataloader.load(user["best_friend"]))
            .then(lambda user: user["name"])
        )

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            name="Query",
            fields={
                "name": GraphQLField(
                    GraphQLString,
                    args={
                        "userId": GraphQLArgument(GraphQLString),
                    },
                    resolve=resolve_name,
                ),
                "bestFriendName": GraphQLField(
                    GraphQLString,
                    args={
                        "userId": GraphQLArgument(GraphQLString),
                    },
                    resolve=resolve_best_friend_name,
                ),
            },
        )
    )

    result = graphql_sync_deferred(
        schema,
        """
        query {
            name1: name(userId: "1")
            name2: name(userId: "2")
            bestFriend1: bestFriendName(userId: "1")
            bestFriend2: bestFriendName(userId: "2")
        }
        """,
    )

    assert not result.errors
    assert result.data == {
        "name1": "Sarah",
        "name2": "Lucy",
        "bestFriend1": "Lucy",
        "bestFriend2": "Geoff",
    }
    assert mock_load_fn.call_count == 2
    assert mock_load_fn.call_args_list[0].args[0] == ["1", "2"]
    assert mock_load_fn.call_args_list[1].args[0] == ["3"]


def test_concurrent_threads_are_isolated():
    """DataloaderBatchCallbacks must isolate callbacks per thread.

    Without thread-local callback storage, _callbacks is a plain list shared
    across all threads. When two threads add callbacks concurrently, both
    threads see the combined list. One thread's run_all_callbacks then steals
    the other's callbacks, leaving SyncFutures permanently PENDING.

    This test verifies isolation at the DataloaderBatchCallbacks level:
    each thread should only see callbacks it added itself.
    """
    from graphql_sync_dataloaders.sync_dataloader import dataloader_batch_callbacks

    add_barrier = threading.Barrier(2, timeout=5)
    check_barrier = threading.Barrier(2, timeout=5)
    visible_counts = {}

    def thread_fn(name):
        # Each thread adds exactly one callback
        dataloader_batch_callbacks.add_callback(lambda: name)
        # Wait until both threads have added their callback
        add_barrier.wait()
        # Check how many callbacks are visible from this thread
        visible_counts[name] = len(dataloader_batch_callbacks._callbacks)
        check_barrier.wait()
        # Clean up: drain this thread's callbacks so they don't leak
        dataloader_batch_callbacks.run_all_callbacks()

    t1 = threading.Thread(target=thread_fn, args=("t1",))
    t2 = threading.Thread(target=thread_fn, args=("t2",))
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    # Without thread-local: both threads see 2 (shared list)
    # With thread-local: each thread sees only 1 (its own)
    assert visible_counts["t1"] == 1, (
        f"t1 saw {visible_counts['t1']} callbacks, expected 1 — callbacks are leaking across threads"
    )
    assert visible_counts["t2"] == 1, (
        f"t2 saw {visible_counts['t2']} callbacks, expected 1 — callbacks are leaking across threads"
    )
