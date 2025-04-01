angular.module("publicpages").controller("MavenMilkCtrl", [
	"$scope",
	"ngDialog",
	"MvnStorage",
	function($scope, ngDialog, MvnStorage) {
		const _storage = [
			{
				id: 0,
				question: "How long can I refrigerate my breast milk for?",
				answer: "According to the CDC, breast milk can be safely refrigerated for up to 4 days."
			},
			{
				id: 1,
				question: "How long can I freeze breast milk for?",
				answer:
					"If it stays frozen the entire time frozen breast milk is best used within 6 months and acceptable to use up to 12 months later according to the CDC. <u>Never refreeze milk that has been thawed</u>. If breast milk thaws, refrigerate and use within 1 day."
			},
			{
				id: 2,
				question: "How much milk does your domestic Pump + Post Kit hold?",
				answer:
					"Each domestic Pump + Post Kit holds up to 36 oz. of breast milk. To fit all 36 oz., follow the packing directions and make sure to remove all excess air from each storage bag."
			},
			{
				id: 3,
				question: "How long will my milk stay refrigerated in a Pump + Post Kit?",
				answer:
					"Each shipping kit has up to 72 hours (3 full days) of refrigeration to keep your milk cold in case of unexpected shipping delays."
			},
			{
				id: 4,
				question: "How much does your international Pump + Check Kit hold?",
				answer: "Each international Pump + Check Kit packs up to 270 oz. of frozen breast milk (or about 9 days worth)."
			},
			{
				id: 5,
				question: "Can I use my Pump + Post Kit as a refrigerator and add more milk before I ship it?",
				answer:
					"The Pump + Post Kit is designed to be kept closed after it has been activated. Please do not open the kit once you have activated the cooling unit and packed the kit."
			}
		]

		const _security = [
			{
				id: 0,
				question: "What are the TSA regulations for breast milk at U.S. airport security checkpoints?",
				answer: `<ul>
				<li>TSA allows travelers to carry unlimited amounts of breast milk through security checkpoints within the United States. However, TSA also has the right to inspect any carry-on so we recommend declaring to TSA that you are carrying a breast pump and breast milk before you start your screening.</li>
				<li>Formula, breast milk, and juice in quantities greater than 3.4 ounces or 100 milliliters are allowed in carry-on baggage and do not need to fit within a quart-sized bag. Remove these items from your carry-on bag to be screened separately from the rest of your belongings.</li>
				<li>Inform the TSA officer at the beginning of the screening process that you carry formula, breast milk and juice in excess of 3.4 ounces in your carry-on bag. These liquids are typically screened by X-ray.</li>
				<li>You do not need to travel with your child to travel with breast milk.</li>
				<li>TSA agents have the right to take away partially frozen gel or ice freezer packs.</li>
				<li>Visit the <a href="https://www.tsa.gov/travel/special-procedures/traveling-children" target="_blank">TSA site</a> for a full list of regulations.</li>
				</ul>`
			},
			{
				id: 1,
				question:
					"Why can I carry breast milk on board when flying internationally out of the U.S., but not on my return flight?",
				answer:
					"While the U.S. airport security rules allow moms to bring breast milk through airport security and carry it on the plane, nearly every other country treats breast milk like any other liquid and requires amounts over 4 oz. to be checked even if it is frozen. In order to avoid hassles or losing your milk, always check your Pump + Check Kit when traveling internationally."
			}
		]

		const _ordering = [
			{
				id: 0,
				question: "How far ahead of time do I need to place my order?",
				answer:
					"To guarantee delivery, Maven Milk orders need to be placed at least one weekday before you arrive at your hotel. FedEx has limited shipping on Saturdays and does not pick up or deliver on Sundays. If you are placing an order for a Monday arrival, please place your order on Thursday."
			},
			{
				id: 1,
				question: "How do I place a Pump + Post Kit order if I’m traveling to multiple destinations in one trip?",
				answer:
					"We are happy to help you with each leg of your trip. Please place a Pump + Post Kit order for each destination individually."
			}
		]

		const _shipping = [
			{
				id: 0,
				question: "Domestic Pump + Post Kit",
				answer: `<ul>
				<li>
					<strong>How do I set up the FedEx shipment back to baby?</strong><br/>
					Our Pump + Post Kits can be sent back home to baby using FedEx Express and the FedEx label included in the kit. The most reliable way to arrange FedEx shipment is to drop your package off directly at your nearest FedEx Office location at least 30 minutes before their last Express pickup deadline. Remember that many FedEx Express pick-ups happen earlier in the day to ensure overnight delivery. FedEx has limited shipping on Saturdays and does not pick up or deliver on Sundays. <a href="https://www.fedex.com/locate/" target="_blank">Use the FedEx Office locator</a> to find the nearest location.
					<br/>
					After dropping your packaged milk off at FedEx, check the tracking within a few hours. If your package doesn’t show up, contact us at <a href="mailto:mavenmilk@mavenclinic.com?subject=Maven Milk Support Request">mavenmilk@mavenclinic.com</a> for assistance.
				</li>
				<li>
					<strong>What do I do if my hotel won’t help me ship back my milk?</strong><br/>
					The most reliable way to ship your milk home is to drop off your package directly at a FedEx drop box or FedEx Office location at least 30 minutes before their last Express pickup deadline. Remember that many FedEx Express pick-ups happen earlier in the day to ensure overnight delivery. To find a FedEx location, use the <a href="https://www.fedex.com/locate/" target="_blank">FedEx Office locator</a>.
				</li>
				<li>
					<strong>How do I find the nearest FedEx for dropping off my Pump + Post Kit?</strong><br/>
					Use the <a href="https://www.fedex.com/locate/" target="_blank">FedEx Office locator</a> to find the nearest drop-off center near your accommodations while travelling.</a>.
				</li>
				<li>
					<strong>How do I ship my Pump + Post Kit if I am staying in an apartment or house instead of a hotel?</strong><br/>
					You will need to drop off your Pump + Post package directly at a FedEx drop box or FedEx Office location at least 30 minutes before their last Express pickup deadline.
				</li>
				<li>
					<strong>Can I ship back my milk on a weekend?</strong><br/>
					Yes, you can ship milk back home on Saturdays but please note that milk sent "overnight" on a Saturday will not arrive back to baby until Monday because FedEx does not pick up or deliver any packages on Sundays. In most locations, Saturday FedEx Express shipping deadlines are early in the day. To find the hours of your nearest FedEx location, use the <a href="https://www.fedex.com/locate/" target="_blank">FedEx Office locator</a> and check for the time of the “Last Express Pickup”.
				</li>
				<li>
					<strong>How early do I need to get my milk to FedEx so that it ships overnight back to baby?</strong><br/>
					We strongly recommend dropping off your milk with FedEx at least 30 minutes before the location’s last pickup deadline (but the earlier in the day the better!). To find the hours of your nearest FedEx location, use the <a href="https://www.fedex.com/locate/" target="_blank">FedEx Office locator</a> and check for the time of the “Last Express Pickup”.
				</li>
				<li>
					<strong>Can I use UPS or a Post Office to send my milk back to my baby?</strong><br/>
					We recommend working with FedEx to ensure reliable delivery. Some UPS stores located in hotels will ship FedEx packages. However, you cannot use the included FedEx label if shipping from a United States Post Office.
				</li>
				<li>
					<strong>What do I do if I miss the pick-up window for my nearest FedEx?</strong><br/>
					Use the <a href="https://www.fedex.com/locate/" target="_blank">FedEx Office locator</a> to find other Express pickup locations and times in your area.

				</li>
				<li>
					<strong>Will all FedEx locations accept my Pump + Post Kit?</strong><br/>
					Yes, all FedEx locations will accept your Pump + Post Kit. The kit can also fit into FedEx drop boxes.
				</li>
				<li>
					<strong>Will my breast milk freeze if I ship it home in winter?</strong><br/>
					No, the Pump + Post Kit will keep your milk at a regulated refrigerated temperature for 72 hours even if the outside temperature is below freezing.
				</li>
				<li>
					<strong>What happens during inclement weather?</strong><br/>
					Occasionally weather and other events can cause unexpected delays in FedEx shipping service. Maven Milk is not responsible for these delays however, each Pump + Post shipping kit is equipped for 72 hours (3 full days) of refrigeration to keep your milk cold in case of unexpected shipping delays.
				</li>
				<li>
					<strong>What happens if my box gets delayed?</strong><br/>
					Contact FedEx via phone (800-463-3339) or online (via their <a href="https://www.fedex.com/en-us/customer-support.html" target="_blank">Customer Support system</a>) to learn the status of your package. Make sure to have your tracking number available for reference. And remember, each Pump + Post shipping kit is equipped with up to 72 hours (3 full days) of refrigeration to keep your milk cold in case of unexpected shipping delays.
				</li>
				<li>
					<strong>What happens if my milk spoils during shipping?</strong><br/>
					Contact Maven Milk Customer Service at <a href="mailto:mavenmilk@mavenclinic.com?subject=Maven Milk Support Request">mavenmilk@mavenclinic.com</a>.

				</li>
				<li>
					<strong>How should I dispose of my breast milk shipping kit packaging?</strong><br/>
					You can recycle the cardboard carton. The cooling unit and styrofoam insert can be discarded in the trash.
				</li>
			</ul>`
			},
			{
				id: 1,
				question: "International Pump + Check Kit",
				answer: `
				<ul>
					<li>
						<strong>Why can’t I ship back my breast milk back internationally?</strong><br/>
						While breast milk can be easily and reliably shipped within the United States, shipping breast milk back to the United States from another country is less seamless. U.S. Customs regularly checks packages coming into the country which causes up to a 2-week delay in shipments. Maven wants to make sure your milk gets home to your baby in a timely fashion and does not spoil. This is why we unfortunately cannot ship breast milk internationally.
					</li>,
					<li>
						<strong>Why can’t I ship the Pump + Check Kit to my international destination?</strong><br/>
						International shipping can result in additional unforeseen delays, which is why Maven Milk only ships to U.S. addresses. You can check your Pump + Check Kit on the flight to your international destination and then check it again on your return trip home.
					</li>
					<li>
						<strong>Are the foam ice packs reusable?</strong><br/>
						Yes, the foam ice packs included in the Pump + Check Kit are reusable.
					</li>
				</ul>`
			}
		]

		const _before = [
			{
				id: 0,
				question: "What questions do I need to ask my hotel before I arrive?",
				answer: `<ul>
						<li>
							<strong>Domestic Pump + Post Kit</strong><br/>
							<ul>
								<li>Request a fridge in your room. Most hotels have refrigerators available, especially for medical reasons.</li>
								<li>Confirm with the hotel where you will pick up your shipping kits when you arrive.</li>
								<li>Ask if there are any fees associated with receiving packages. (Many hotels, especially conference centers, will charge fees to your room.)</li>
							</ul>
							<strong>International Pump + Check Kit</strong><br/>
							<ul>
								<li>Request a fridge in your room. Many hotels have refrigerators available, especially for medical reasons.</li>
								<li>When you arrive, see if the hotel can help you freeze your breast milk and foam ice packs.</li>
							</ul>
						</li>
					</ul>`
			},
			{
				id: 1,
				question: "What do I need to bring with me to pump while traveling?",
				answer: `<ul>
					<li>Pack your favorite travel pump and milk cooler bag.</li>
					<li>Pumping on the go is a lot easier if you don’t need an outlet. Consider bringing batteries or a manual hand pump.</li>
					<li>Pack your pump cleaning supplies.</li>
					<li>If you are traveling internationally, don’t forget an international adapter.</li>
				</ul>`
			}
		]

		const _packing = [
			{
				id: 0,
				question: "Domestic Pump + Post Kit:",
				answer: `
					<ul>
						<li>
							<strong>Do I have to use the breast milk storage bags included in the Pump + Post Kit or can I use my own preferred bags?</strong><br/>
							Each Pump & Post Kit comes with (6) 6 oz. Lansinoh breast milk storage bags (and (1) extra just in case!). If you want to use your own bags, you will need (6) bags per kit.
						</li>
						<li>
							<strong>Can I use the Pump + Post Kit to ship frozen milk?</strong><br/>
							No, the Pump + Post Kit is intended to only ship refrigerated milk. The Pump + Post Kit will keep milk at a refrigerated temperature for 72 hours. Frozen milk will thaw as it ships back to baby. Should you encounter a shipping delay, this would exceed the CDC’s guideline to only use thawed breast milk within one day.
						</li>
						<li>
							<strong>How do I pack the Pump + Post Kit?</strong><br/>
							Follow the directions included in your Pump + Post Kit. Make sure all milk is refrigerated before packing the kit. Fill and label up to (6) bags with up to 6 oz. of milk each for a total of up to 36 oz. of milk. Remove all excess air from each bag. Fold each bag below the seal and place them in the cooler so each bag overlaps the one underneath it. Do not overfill.
						</li>
						<li>
							<strong>What do I do if there is a “NanoCool” logo on my cooling pack before I hit the activation button?</strong><br/>
							Do not be alarmed if the “NanoCool” logo is visible on the Pump + Post Kit’s cooling pack. The logo is temperature-activated and can be activated by the cool temperatures while it ships to you. If the button on the underside of the cooling pack has not been activated, the cooling pack is still fully functional and ready to work for you when you pack up your shipping kit.
						</li>
			`
			},
			{
				id: 1,
				question: "Domestic Pump + Carry Packs:",
				answer: `<ul>
						<li>
							<strong>Are the foam ice packs reusable?</strong><br/>
							Yes, the foam ice packs in the Pump + Carry Packs are reusable.
						</li>
					<ul>
				`
			},
			{
				id: 2,
				question: "International Pump + Check Kit:",
				answer: `<ul>
						<li>
							<strong>How do I pack the Pump + Check Kit?</strong><br/>
							Follow the directions included in your Pump + Check Kit to ensure milk stays as cold as possible during your trip. Make sure your milk is frozen solid and that your ice packs have been frozen at least 72 hours before you pack for optimal performance.
						</li>
						<li>
							<strong>Does the Pump + Check Kit come with breast milk storage bags?</strong><br/>
							No, the reusable Pump + Check Kit is designed so you can reuse it as many times as you need it and it does not come with breast milk storage bags. Bring your favorite breast milk storage bags for each trip as needed. This kit can hold up to (45) 6-oz. bags when packed according to the instructions.
						</li>
					<ul>
				`
			}
		]

		const _customerService = [
			{
				id: 0,
				question: "Have additional questions?",
				answer:
					'Contact Maven Milk Customer Service for more information: <a href="mailto:mavenmilk@mavenclinic.com?subject=Maven Milk Support Request" target="_blank">mavenmilk@mavenclinic.com</a>.'
			}
		]

		var installParams = MvnStorage.getItem("local", "mvnInst")
				? JSON.parse(MvnStorage.getItem("local", "mvnInst"))
				: null,
			installAttrs = installParams ? installParams : {}

		$scope.activeFaq = [0, 0]
		$scope.mmFaqTitles = [
			"Storage & Refrigeration",
			"Security",
			"Ordering",
			"Shipping",
			"Before Travel",
			"Packing your Kit",
			"Contact us"
		]
		$scope.mmFaqs = [_storage, _security, _ordering, _shipping, _before, _packing, _customerService]

		$scope.openEntContact = function() {
			ngDialog.open({
				template: "/js/mvnApp/public/enterprise/_enterprise-contact.html",
				className: "mvndialog",
				scope: true,
				controller: [
					"$scope",
					function($scope) {
						$scope.instParams = installAttrs
					}
				]
			})
		}
	}
])
