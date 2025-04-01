# Glidepath

## Purpose
The `glidepath` package provides a collection of utilities that automatically apply Mono best practices during tests.
Glidepath does not introduce application exceptions when 
instrumented thresholds are exceeded at runtime.

## Tools

### .respond() | Generator[None, None, None]
Used in API handlers to wrap the serialization of response data. It enforces that no db calls are made to construct the response.


### .guard_commit_boundary() | Generator[None, None, None]
Wrap a scope of actions that define a bounded set of work. This of it like
repository scoped `Unit of Work` that can be arbitrarily applied to any scope,
including UOW's.  Within this scope all ORM objects dirtied MUST be committed or
rolled back. On scope exit `rollback()` will be called explicitly. This ensures
that when under test, post run queries will be served data guaranteed to be
persisted (which is the test writers assumption but not an invariant).

```python
def service_func(id: int) -> CoolObject:
  obj = CoolModel(id=id)
  return obj

def test_thingy():
  # create the new cool object
  test_id: int = 123
  new_obj = service_func(id=123)
  # note that it has not been committed yet....

  found_obj = db.session.query(CoolModel).filter(CoolModel.id==test_id).one()
  assert found_obj is not None # <-- This will pass 
  assert found_obj == new_obj # <-- This will pass 
  
# .... but in production the new_obj created would be rolled back (without error) 
# as the task or API call completes, creating unexpected behavior (dataloss). All 
# logs and metrics will indicate the object has successfully been created but it 
# wont appear in the database on subsequent queries.
```

During test time, at the scope exit of a `guard_commit_boundary`, any dirty ORM objects
will force an executing test to fail. This is not a 100% perfect solution... If
the code path under test conditionally creates/modifies ORM objects and that
condition is not met, the test will still pass because 0 objects were left
dirty. This is analogous to missing a test for a block of application behavior.

The `guard_commit_boundary` decorator only interferes at test time. It has no effect on
normal application operation. To ensure this, glidepath.guard_commit_boundary()
evaluation and assertion tooling is implemented in a separate file and installed
in `pytest` set up through unittest.mock wiring during test execution.

A guarded boundary may appear at any depth of the execution flow and may be
nested within parent scopes. The only requirement enforced is that objects
dirtied (create/add/flush) by this scope are explicitly committed or rolled back
prior to scope exit.


##### Examples include:
- Actions taken between the input parse and the response serialization in a API
  handler that may modify db rows. This usually applies to all
  PUT/POST/PATCH/DELETE endpoints but can also apply to GET depending on the
  implementation.
  ```python
  from glidepath import glidepath

  # .../resources/example.py
  def post(self):
      # ...
      args = schema_in.load(request.args).data
      # ...
      results = services.handle_new_thing(args)
      # ...
      return schema_out.dump(results).data
  
  # .../services/example.py
  @glidepath.guard_commit_boundary()
  def handle_new_thing(args: SchemaIn):
      new_thing = NewThing(**args)
      db.session.add(new_thing)
      db.session.commit() # <-- glidepath will ensure we commit the new obj
  ```
- Job (task) function (decorated as @job...) that may conditionally modify DB
  rows. This is almost universally true for all mono jobs.
  ```python
    @retryable_job(...)
    @glidepath.guard_commit_boundary()
    def some_cool_job() -> None:
      # ...
      # call any number of dependents
      # ...
      return None # <-- glidepath will ensure no objects will be lost to rollback()
      
  ```
- Any function that has multiple evaluation steps and/or model changes that should be
  all committed as a group or all rolled back (transactional scope).
  ```python
  @glidepath.guard_commit_boundary()
  def multi_step_job() -> CoolModel:
    obj = CoolModel()
    
    change_something(obj)
    change_something_else(obj)

    db.session.commit() # <-- glidepath will ensure this is not omitted
    return obj
  
  def change_something(obj: CoolModel) -> None:
    if something:
      obj.foo = "bar"
      db.session.add(obj) # <-- glidepath will ensure this is not omitted
  
  def change_something_else(obj: CoolModel) -> None:
    if something:
      obj.baz = "bar"
      db.session.add(obj) # <-- glidepath will ensure this is not omitted
  ```
- Any scope that wishes to (test time) guard that the DB interaction hygiene has
  been maintained by all of its dependents. 
  ```python
  @glidepath.guard_commit_boundary()
  def call_other_service_functions() -> None:
      another_team_service.do_something()
      shared_service.do_something_else()
      # glidepath will ensure that the above service functions maintain proper 
      # commit hygiene and wont allow this scope to exit with dirty ORM objects.
      return None  
  ```

### Guidance on add/flush/commit
TODO... I would like to source broader suggestions beyond my own. I'll reach out
to some individuals to open MRs to add their suggestions here.
