# Maven AuthN
This package service as the central library for our Authentication Domain. 

Authentication is responsible for:
- User creation
- User login
- Session management

Authentication is NOT related to Authorization. 

_Authentication_ is the means by which we create or determine an identity.

_Authorization_ is a means by which we determine what an identity is allowed to do.

[Here](https://www.linkedin.com/pulse/authn-top-authz-bottom-ron-kuris/) is a decent blog post discussing the 
responsibilities of these two concepts.

[Here](https://www.jmgundersen.net/blog/authorisation-patterns-for-monoliths-and-microservices) is an excellent deep 
dive into different authorization patterns for microservices.