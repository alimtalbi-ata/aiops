# Legacy retirement policy

The new runtime must not coexist as a second logical AioOps platform. Before acceptance, the old containers are stopped and their metadata archived. The retirement script never deletes legacy volumes or images.

Do not manually delete old data until the new stack has passed backup verification, functional E2E, resilience tests and business acceptance.
