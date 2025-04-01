# Repository and unit-of-work pattern explained

Refer to the documentation located [here](https://medium.com/@edin.sahbaz/implementing-the-unit-of-work-pattern-in-clean-architecture-with-net-core-53efb7f9d4d) for some of the ideas behind the logic.

In the ORM paradigm, a session is conceptually a unit of work. It is up to the caller to `commit` or `rollback` at appropriate occasions.

## What problems we have now?

In our repository `base.py` implementation, the class instance will grab one session if there is no passed in `session` object. Conceptually, it is the differentiation of the simple `Repository` pattern vs. the `Unit-of-Work plus Repository` pattern. Unfortunately, the idea is not well conveyed to engineers and we have seen misconceptions around how the repository pattern would work.

For example, some engineers think the `Repository` instance will automatically persist the create/update/delete changes to database. And some other engineers just blindly pass in the `session` object when initializing a repository instance without knowing that they have to explicitly commit/rollback at necessary occasions. Even if the `session.commit()` call is eventually made, it may not be at the desired moment per the `transaction` concept, one example is giving below.
```[sample code]
session = db.session
repo_1 = MyAwesomeRepository_1(session)
repo_1.create(myAwesomeObject)
session.add(myAwesomeTable_2)
make_some_external_calls_to_grab_more_data
do_bunch_validations
if validation failed:
  session.rollback()
  return 400
# all good
session.execute(update myAwsomeTable_3)
session.commit()
```
In the above example, my session will commit when everything runs as expected. However, if something fails, everything will be rolled back but in a lot of the scenarios, I still want to at least create a record in DB for my first awesome object. In another word, the logic should be wrapped in different transactions instead of one big transaction.

## What is the proposal going forward?

To make sure we address the issues mentioned above and make the `Repository` or `Repository + uow` choice explict, a new `is_in_uow` flag is added to the repository base class initializer. With the change, the default behavior for the `Repository` pattern is that any create/update/delete actions will be immediately committed to DB unless the caller explicitly mentions the `uow` pattern is used.

With this new approach, there are two paradigms
1. Simple repository pattern (`is_in_uow=False`)

In this scenario, each create/update/delete action is by itself a simple DB transaction and we will commit immediately.

2. Repository + UOW pattern

It is the caller's responsibility to make sure the `session.commit()/rollback()` logic is called at the right place.

## Multiple repositories in one unit-of-work
A repository wraps operations in one table. It is common that there are DB operations across multiple tables wrapped by multiple repositories that we want to include in one transaction, so we need to make these repositories in one unit-of-work.

SQLAlchemyUnitOfWork supports multiple repositories. For example:
```[sample code]
with SQLAlchemyUnitOfWork(repository_classes=[RepoTypeOne, RepoTypeTwo]) as uow:
    repo_one = now.get_repo(RepoTypeOne)
    repo_two = now.get_repo(RepoTypeTwo)
    
    repo_one.create(....)
    repo_two.update(.....)
    repo_two.delete(.....)
    
    uow.commit()
```