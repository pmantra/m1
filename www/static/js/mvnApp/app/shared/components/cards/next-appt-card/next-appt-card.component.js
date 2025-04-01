function NextApptCardController(Appointments, Plow) {
	const vm = this
	
	vm.$onInit = () => {
		vm.apptAction = vm.data.actions[0]
		
		Appointments.getAppointment(vm.apptAction.appointment_id).get().then(appointment => {
			vm.nextAppt = appointment
			_parseStartTime()
		})
	}
	
	vm.sendEvent = actionType => {
		const evt = {
			"event_name" : vm.data.analytics_name,
			"action_type": vm.apptAction.type,
			"user_id" : vm.user.id
		}
		Plow.send(evt); 
	}
	
	const _parseStartTime = () => {
		vm.startsIn10 = moment(vm.nextAppt.scheduled_start).subtract('10', 'minutes').format('YYYY-MM-DD HH:mm:ss') <= moment().utc().format('YYYY-MM-DD HH:mm:ss') && (moment(vm.nextAppt.scheduled_end).format('YYYY-MM-DD HH:mm:ss') >= moment().utc().format('YYYY-MM-DD HH:mm:ss'))
		vm.hasStarted = (moment(vm.nextAppt.scheduled_start).format('YYYY-MM-DD HH:mm:ss') < moment().utc().format('YYYY-MM-DD HH:mm:ss')) &&  (moment(vm.nextAppt.scheduled_end).format('YYYY-MM-DD HH:mm:ss') >= moment().utc().format('YYYY-MM-DD HH:mm:ss'))
		vm.hasFinished = (vm.nextAppt.member_ended_at && vm.nextAppt.practitioner_ended_at);
	}
}

angular.module('app').component('nextApptCard', {
	templateUrl: '/js/mvnApp/app/shared/components/cards/next-appt-card/_next-appt-card.html',
	controller: NextApptCardController,
	bindings: {
		data: '=',
		user: '='
	}
})
