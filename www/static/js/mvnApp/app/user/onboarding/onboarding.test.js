/* Onboarding controller tests */

/*
describe('Onboarding controller::', function(){

	var $controller,
		scope,
		userService,
		noSession,
		Restangular,
		$state,
		
		lifeStage;

	beforeEach(function() {
		module('ui.router');
		module('ngDialog');
		module('ngNotify');
		module('restangular');
		module('mavenApp');
		module('app');
		module('user');
		angular.module('mavenApp').constant("config", "{}")
		angular.module('mavenApp').constant("APIKEY", "12345")
	});

	beforeEach(angular.mock.inject(function($controller, $rootScope, _$state_, _$httpBackend_, _Restangular_, _Users_, _noSession_){
		scope = $rootScope.$new();
		userService = _Users_;
		Restangular = _Restangular_;
		noSession = _noSession_;
		httpBackend = _$httpBackend_;
		$state = _$state_;

		spyOn($state, 'go');

		scope.user = {
			"first_name": "Jane",
			"last_name": "Doe",
			"email": "test@test.com",
			"id": 123,
		}
		
		$controller('OnboardingCtrl', { $scope: scope, Restangular: Restangular, noSession: noSession, $state: $state });
	}));

	describe('Go to onboarding step', function() {
		it('Should go to step with id', function() {
			scope.obStep = {
				step : '1'
			}
			scope.goToStep('3');
			expect(scope.obStep.step).toEqual('3');
		})
	})	

	describe('Set life stage', function() {

		it('Handles first-pregnancy case', function() {
			lifeStage =  {
				"name": "first-pregnancy",
				"title": "I'm pregnant–first time mama",
				"stage": {
					"id": 1,
					"name": "pregnant"
				},
			 	"icon": "https://storage.googleapis.com/maven-prod-svg/enterprise-onboarding-lifestages/first-pregnancy.svg"
			}

			scope.setLifeStage(lifeStage);

			expect(scope.userCase.ispartner).toBeFalse;
			expect(scope.userCase.reason).toBeFalse;
			expect($state.go).toHaveBeenCalled();
			expect($state.go).toHaveBeenCalledWith('app.onboarding.stage', scope.userCase);

		});

		it('Handles subsequent-pregnancy case', function() {
			lifeStage =  {
				"name": "subsequent-pregnancy",
				"title": "I'm pregnant again",
				"stage": {
					"id": 1,
					"name": "pregnant"
				},
				"icon": "https://storage.googleapis.com/maven-prod-svg/enterprise-onboarding-lifestages/subsequent-pregnancy.svg"
			},

			scope.setLifeStage(lifeStage);

			expect(scope.userCase.ispartner).toBeFalse;
			expect(scope.userCase.id).toEqual(1);
			expect(scope.userCase.reason).toBeFalse;
			expect($state.go).toHaveBeenCalled();
			expect($state.go).toHaveBeenCalledWith('app.onboarding.stage', scope.userCase);

		});

		it('Handles new-mom (first time) case', function() {
			lifeStage = {
				"name": "new-mom",
				"title": "Just had my first baby",
				"stage": {
					"id": 2,
					"name": "new-mom"
				},
				"icon": "https://storage.googleapis.com/maven-prod-svg/enterprise-onboarding-lifestages/new-mom.svg"
			}

			scope.setLifeStage(lifeStage);

			expect(scope.userCase.ispartner).toBeFalse;
			expect(scope.userCase.id).toEqual(2);
			expect(scope.userCase.reason).toBeFalse;
			expect($state.go).toHaveBeenCalled();
			expect($state.go).toHaveBeenCalledWith('app.onboarding.stage', scope.userCase);

		});

		it('Handles mom case', function() {
			lifeStage = {
				"name": "mom",
				"title": "Just had another baby",
				"stage": {
					"id": 2,
					"name": "new-mom"
				},
				"icon": "https://storage.googleapis.com/maven-prod-svg/enterprise-onboarding-lifestages/mom.svg"
			},

			scope.setLifeStage(lifeStage);

			expect(scope.userCase.ispartner).toBeFalse;
			expect(scope.userCase.id).toEqual(2);
			expect(scope.userCase.reason).toBeFalse;
			expect($state.go).toHaveBeenCalled();
			expect($state.go).toHaveBeenCalledWith('app.onboarding.stage', scope.userCase);

		});

		it('Handles partner-pregnant case', function() {
			lifeStage = {
				"name": "partner-pregnant",
				"title": "My partner is pregnant",
				"stage": {
					"id": 1,
					"name": "partner-pregnant"
				},
				"ispartner": true,
				"icon": "https://storage.googleapis.com/maven-prod-svg/enterprise-onboarding-lifestages/partner-pregnant.svg"
			};

			scope.setLifeStage(lifeStage);

			expect(scope.userCase.ispartner).toBeTrue;
			expect(scope.userCase.id).toEqual(1);
			expect(scope.userCase.reason).toBeFalse;
			expect($state.go).toHaveBeenCalled();
			expect($state.go).toHaveBeenCalledWith('app.onboarding.stage', scope.userCase);

		});

		it('Handles partner-new-mom case', function() {
			lifeStage = {
				"name": "partner-new-mom",
				"title": "My partner is a new mom",
				"stage": {
					"id": 2,
					"name": "new-parent"
				},
				"ispartner": true,
				"icon": "https://storage.googleapis.com/maven-prod-svg/enterprise-onboarding-lifestages/partner-new-mom.svg"
			};

			scope.setLifeStage(lifeStage);
			expect(scope.userCase.ispartner).toBeTrue;
			expect(scope.userCase.id).toEqual(2);
			expect(scope.userCase.reason).toBeFalse;
			expect($state.go).toHaveBeenCalled();
			expect($state.go).toHaveBeenCalledWith('app.onboarding.stage', scope.userCase);

		});

		it('Handles fertility case', function() {
			lifeStage = {
				"name": "fertility",
				"title": "I'm using or considering IUI/IVF",
				"stage": {
					"id": 3,
					"name": "fertility"
				},
				"reason": "fertility",
				"icon": "https://storage.googleapis.com/maven-prod-svg/enterprise-onboarding-lifestages/trying.svg"
			};

			scope.setLifeStage(lifeStage);
			expect(scope.userCase.ispartner).toBeFalse;
			expect(scope.userCase.reason).toBe("fertility");
			expect($state.go).toHaveBeenCalled();
			expect($state.go).toHaveBeenCalledWith('app.onboarding.verify-enterprise', scope.userCase);

		});

		it('Handles loss case', function() {
			lifeStage = {
				"name": "pregnancyloss",
				"title": "I've experienced a loss",
				"reason": "pregnancyloss",
				"icon": "https://storage.googleapis.com/maven-prod-svg/enterprise-onboarding-lifestages/experienced-loss.svg"
			};

			scope.setLifeStage(lifeStage);
			expect(scope.userCase.ispartner).toBeFalse;
			expect(scope.userCase.reason).toBe("pregnancyloss");
			expect($state.go).toHaveBeenCalled();
			expect($state.go).toHaveBeenCalledWith('app.onboarding.verify-enterprise', scope.userCase);

		});

		it('Handles surrogacy case', function() {
			lifeStage = {
				"name": "surrogacy",
				"title": "I'm using a surrogate",
				"reason": "surrogacy",
				"icon": "https://storage.googleapis.com/maven-prod-svg/enterprise-onboarding-lifestages/surrogacy.svg"
			}

			scope.setLifeStage(lifeStage);
			expect(scope.userCase.ispartner).toBeFalse;
			expect(scope.userCase.reason).toBe("surrogacy");
			expect($state.go).toHaveBeenCalled();
			expect($state.go).toHaveBeenCalledWith('app.onboarding.verify-enterprise', scope.userCase);

		});

		it('Handles adopting case', function() {
			lifeStage = {
				"name": "adopting",
				"title": "I'm adopting",
				"reason": "adopting",
				"icon": "https://storage.googleapis.com/maven-prod-svg/enterprise-onboarding-lifestages/adopting.svg"
			}

			scope.setLifeStage(lifeStage);
			expect(scope.userCase.ispartner).toBeFalse;
			expect(scope.userCase.reason).toBe("adopting");
			expect($state.go).toHaveBeenCalled();
			expect($state.go).toHaveBeenCalledWith('app.onboarding.verify-enterprise', scope.userCase);

		});

		it('Handles egg_freezing case', function() {
			lifeStage = {
				"name": "egg_freezing",
				"title": "I want to freeze my eggs",
				"stage": {
					"id": 4,
					"name": "egg_freezing"
				},
				"reason": "egg_freezing",
				"icon": "https://storage.googleapis.com/maven-prod-svg/enterprise-onboarding-lifestages/egg-freezing.svg"
			}

			scope.setLifeStage(lifeStage);
			expect(scope.userCase.ispartner).toBeFalse;
			expect(scope.userCase.reason).toBe("egg_freezing");
			expect($state.go).toHaveBeenCalled();
			expect($state.go).toHaveBeenCalledWith('app.onboarding.verify-enterprise', scope.userCase);

		});


		it('Handles all other case', function() {
			lifeStage = {
				"name": "other",
				"title": "None of these apply to me",
				"reason": "other",
				"icon": "https://storage.googleapis.com/maven-prod-svg/enterprise-onboarding-lifestages/other.svg"
			}

			scope.setLifeStage(lifeStage);
			expect(scope.userCase.ispartner).toBeFalse;
			expect(scope.userCase.reason).toBe("other");
			expect($state.go).toHaveBeenCalled();
			expect($state.go).toHaveBeenCalledWith('app.onboarding.verify-enterprise', scope.userCase);

		});

	})

});*/