
describe('Users service tests', function(){
    var userService,
        Restangular,
        $httpBackend,
        noSession;

    beforeEach(function() {
        module('mavenApp');
        module('ui.router');
        module('user');
    });

    

    beforeEach(inject(function (_Users_) {
        userService = _Users_;
      }));
   
    it('Users service should exist', function() {
        expect(userService).toBeDefined();
    })
   
})