"use strict"

/**
 * @ngdoc function
 * @name public.controller:PressCtrl
 * @description
 * # PressCtrl
 * Controller of the public
 */
angular.module("publicpages").controller("PressCtrl", [
	"$scope",
	function($scope) {
		var pressData = [
			{
				title: "CEO of Maven Clinic Credits Success to Career as a Journalist",
				company: "Business Insider",
				url: "https://www.businessinsider.com/ceo-of-maven-clinic-credits-success-to-career-as-journalist-2019-10",
				date: "2019-10-25",
				snippet:
					"The woman who founded Maven explains how her first career taught her 2 key skills that fueled the rise of the $87 million digital health startup.",
				logo: "/img/press/logos/bi.png"
			},
			{
				title: "Digital Health 150: The Digital Health Startups Redefining The Healthcare Industry",
				company: "CB Insights",
				url: "https://www.cbinsights.com/research/digital-health-startups-redefining-healthcare/",
				date: "2019-10-02",
				snippet:
					"Virtual care clinics such as Maven Clinic are also helping women gain better access to providers that cater specifically to women’s health needs and concerns. Maven raised a $27M Series B round in September 2018 with participating investors including Sequoia Capital and Oak HC/FT Partners, among others.",
				logo: "/img/press/logos/cbi.png"
			},
			{
				title:
					"Digital Health The 100 Women Building America's Most Innovative and Ambitious Businesses: The Digital Health Startups Redefining The Healthcare Industry",
				company: "Inc",
				url: "https://www.inc.com/most-innovative-women-2019.html",
				date: "2019-09-16",
				snippet:
					"Kate Ryder is helping companies retain their most valuable asset: employees. New mothers who use Maven, the digital health clinic Ryder founded in 2014, are more likely to remain in the workplace, she says. The health app lets women connect with more than 1,500 health practitioners for a variety of services, including birth-control prescriptions, breast-milk shipping, and treatments for post-partum depression. Maven’s data shows that 90 percent of its users return to work on time after having a baby, compared with the national average of 57 percent. Its platform is available to individuals on a per-session basis, and also for companies and health plans looking to enrich their benefits. Snapchat’s parent company, Snap, is already on board. With more than $42 million in funding, Maven has helped more than two million people get access to health care.",
				logo: "/img/press/logos/inc.png"
			},
			{
				title: "How Maven is working to close the gap in women’s wellness",
				company: "Today",
				url: "https://www.today.com/video/how-maven-is-working-to-close-the-gap-in-women-s-wellness-64970309790",
				date: "2019-07-31",
				snippet:
					"NBC’s Maria Shriver spotlights Maven, a digital on-demand health care company giving patients access to help anytime and anywhere. Later, Kate Ryder, Maven founder and CEO, and Dr. Tia Powell, a psychiatrist and bioethicist at Albert Einstein College of Medicine, talk more on the 3rd hour of TODAY about Maven’s mission.",
				logo: "/img/press/logos/today.png"
			},
			{
				title: "53 Women-Led Startups Disrupting HealthTech",
				company: "Forbes",
				url:
					"https://www.forbes.com/sites/allysonkapin/2019/06/19/50-women-led-startups-disrupting-healthtech/#3673228730d3",
				date: "2019-06-19",
				snippet:
					"If we’re going to solve the biggest health challenges facing this world, then investors must fund diverse founders. Because as you read this, innovations that could be literally saving lives are being left underfunded. Here is a list of 50+ women-led startups disrupting healthtech.",
				logo: "/img/press/logos/forbes.png"
			},
			{
				title: "The Telemedicine Startup Closing the Gap in Women's Health Care",
				company: "Bloomberg",
				url:
					"https://www.bloomberg.com/news/videos/2019-05-01/the-telemedicine-startup-closing-the-gap-in-women-s-health-care-video",
				date: "2019-05-01",
				snippet:
					"Kate Ryder, Maven Clinic founder and chief executive officer, discusses the startup's telemedicine services for women with Bloomberg's Emily Chang on Bloomberg Technology.",
				logo: "/img/press/logos/bloomberg.png"
			},
			{
				title: "40 Under 40: Katherine Ryder",
				company: "Crain's",
				url: "https://www.crainsnewyork.com/awards/40-under-40-2019-katherine-ryder",
				date: "2019-03-25",
				snippet:
					"In 2014 Ryder launched Maven, an app women could use to video-chat with doctors ranging from gynecologists to mental health counselors. Since then she has guided Maven’s shift away from individual consumers to the growing market of employers looking for ways to support employees through fertility treatments, pregnancy, postpartum care and their return to work. Maven is in the process of contracting with insurance plans.",
				logo: "/img/press/logos/crains.png"
			},
			{
				title: "5 Questions with Maven CEO Katherine Ryder",
				company: "Brandchannel",
				url: "http://www.brandchannel.com/2018/05/07/5-questions-maven-ceo-katherine-ryder/",
				date: "2018-05-07",
				snippet:
					"For Maven specifically, success in five years means fixing the problem you outlined earlier—i.e., enabling women everywhere to get the information they need, affordably, to help them make good healthcare decisions for themselves and for their families.",
				logo: "/img/press/logos/brandchannel.png"
			},
			{
				title: "The Boss: How Kate Ryder Started a Healthcare App Designed for Women",
				company: "TIME",
				url: "http://time.com/5240071/kate-ryder-maven-healthcare-app-founder/",
				date: "2018-04-18",
				snippet:
					"Working families get unlimited access to the Maven network, as well as a maternity or fertility concierge to help them navigate everything from disability benefits to childcare options to egg freezing discounts. The draw for companies? They get better retention of valuable employees and a reduction of costs in one of the most expensive areas of care.",
				logo: "/img/press/logos/time.png"
			},
			{
				title: "10 Female Founded Start Ups That Are Expected to Take Off in 2018",
				company: "Business Insider",
				url: "http://www.businessinsider.com/women-founded-startups-expected-to-take-off-in-2018-2018-3",
				date: "2018-04-03",
				snippet:
					"Maven's app connects women to healthcare practitioners through video and private messaging and provides a community centered on women's health.",
				logo: "/img/press/logos/bi.png"
			},
			{
				title: "Maven Clinic: On Demand Healthcare for Women",
				company: "Yahoo Finance",
				url: "https://finance.yahoo.com/video/maven-clinic-demand-healthcare-women-221402267.html",
				date: "2018-02-28",
				snippet:
					"Before Buffett, Bezos and Dimon decided to try their hand at disrupting healthcare, startup Maven Clinic had a head start. Founder and CEO Kate Ryder discusses on The Final Round."
			},
			{
				title: "Fast Company’s Most Innovative Companies",
				company: "Fast Company",
				url: "https://www.fastcompany.com/company/maven",
				date: "2018-02-27",
				snippet:
					"Maven partners with clinics around the country for fertility assistance services, including IVF and egg freezing, and also offers back-to-work management training with career coaches who specialize in parenthood transitions.",
				logo: "/img/press/logos/fastco.png"
			},
			{
				title: "Maven helps draw investors to women’s health",
				company: "The Sunday Times",
				url: "https://www.thetimes.co.uk/article/maven-helps-draw-investors-to-womens-health-q68xt6v6w",
				date: "2018-02-11",
				snippet:
					"Katherine Ryder saw how little help there was for expectant mothers and hatched a solution: Maven. Her digital clinic would be there to help women during pregnancy, after childbirth and with returning to work.",
				logo: "/img/press/logos/thetimes.png"
			},
			{
				title: "The question we ask every mom (but never dads)",
				company: "Quartz at Work",
				url: "https://work.qz.com/1174454/nobody-ever-asks-my-husband-how-do-you-do-it-all/",
				date: "2018-01-08",
				snippet:
					"You need good back-to-work programs and manager training – that’s a core part of our maternity program at Maven and how we work with companies. You need to help the culture of a company understand the pregnancy penalty and the issues moms face.",
				logo: "/img/press/logos/quartz.png"
			},
			{
				title: "Health Tech Founder Shares Her Six Predictions For Women’s Health In 2018",
				company: "Forbes",
				url:
					"https://www.forbes.com/sites/break-the-future/2018/01/05/health-tech-founder-shares-her-six-predictions-for-womens-health-in-2018/",
				date: "2018-01-05",
				snippet:
					"At Maven we’re seeing more and more companies extending paid leave for both parents, funding breastmilk shipments for traveling moms, and introducing return-to-work programs to help new moms phase back into the workforce after leave.",
				logo: "/img/press/logos/forbes.png"
			},
			{
				title: "The CEO Behind The App Revolutionising Women’s Access To Healthcare",
				company: "The Lifestyle Edit",
				url: "http://www.thelifestyleedit.com/katherine-ryder-maven-clinic/",
				date: "2017-10-05",
				snippet:
					"Maven Maternity is our corporate benefits program that focuses not just on providing more support for pregnant working moms, but also on helping women get back on their feet after having a baby and helping them through the transition back to work, which can be quite stressful. We also have programming for new dads, adoptive parents, surrogates, and tracks for infertility, egg freezing, and pregnancy loss. “Starting a family” means so many different things to people!\n\n",
				logo: "/img/press/logos/thelifestyleedit.png"
			},
			{
				title: "How Kate Ryder Went From Journalist To VC To Health Care Founder—Before Age 35",
				company: "Girlboss",
				url: "https://www.girlboss.com/girlboss/girlboss-radio-interview-kate-ryder",
				date: "2017-09-13",
				snippet:
					"Women drive 80 percent of [health care] decision making. Millennial women outspend men by 70 percent. So women are the core drivers, but there were no products at all for women. I started talking to some women’s health providers, and family health providers, like nurse practitioners and doulas and lactation consultants and midwifes.",
				logo: "/img/press/logos/girlboss.png"
			},
			{
				title: "This Startup Landed a $11 Million Series A to Disrupt Women’s Health Care",
				company: "Fortune",
				url: "http://fortune.com/2017/07/25/womens-health-startup-maven/",
				date: "2017-07-25",
				snippet:
					"Maven founder Katherine Ryder hopes such stories will soon become more common. On Tuesday, the company announced a $10.8 million Series A round, bringing the company’s total funding to over $15 million.",
				logo: "/img/press/logos/fortune.png"
			},
			{
				title: "No More Free Birth Control in the Age of Trump? Not If These Women’s Health Initiatives Can Help It",
				company: "Vogue",
				url: "http://www.vogue.com/article/free-birth-control-contraception-planned-parenthood-trump-law-rule",
				date: "2017-06-09",
				snippet:
					"Her company is monitoring this potential new [legislative] development to help women get access to care that they need.",
				logo: "/img/press/logos/vogue.png"
			},
			{
				title: "Katherine Ryder: Maven Clinic Founder and CEO",
				company: "The Bump",
				url: "https://www.thebump.com/a/katherine-ryder",
				date: "2017-05-11",
				snippet:
					"For too long, maternity has been defined as a nine-month health experience that stops the second you have a baby...That couldn’t be further from the truth",
				logo: "/img/press/logos/thebump.png"
			},
			{
				title: "The Startup Digitizing Women’s Healthcare",
				company: "Goop",
				url: "http://goop.com/the-startup-digitizing-womens-healthcare/",
				date: "2017-05-10",
				snippet: "The user experience in beautiful and blessedly simple",
				logo: "/img/press/logos/goop.png"
			},
			{
				title: "5 Women on What It’s Actually like to Work in Tech",
				company: "Coveteur",
				url: "http://coveteur.com/2017/03/20/women-in-tech-industry-share-personal-experiences/",
				date: "2017-03-21",
				snippet:
					"But there are certain companies in technology that just fundamentally don’t support women, so don’t work at them.",
				logo: "/img/press/logos/coveteur.png"
			},
			{
				title: "This App Is Revolutionizing How Women Access Health Care",
				company: "Coveteur",
				url: "http://coveteur.com/2017/03/16/katherine-ryder-maven-app-founder-ceo-womens-health-care/",
				date: "2017-03-16",
				snippet:
					"Maven, at its core, is about building networks of people and then building technology products to connect them.",
				logo: "/img/press/logos/coveteur.png"
			},
			{
				title: "Restoring the Human Element of Health Care: Online",
				company: "HuffPost",
				url: "https://www.huffingtonpost.com/hope-yates/restoring-the-human-eleme_b_5755278.html",
				date: "2017-02-06",
				snippet:
					"It’s time to demand more of the relationship between technology and health. It should be interactive and personalized, and it should leave you feeling empowered, not anxious.",
				logo: "/img/press/logos/huffpost.png"
			},
			{
				title: "Be Inspired By These Creative Leaders Who Are Changing The World",
				company: "Fast Company",
				url:
					"https://www.fastcompany.com/3067011/most-creative-people/be-inspired-by-these-creative-leaders-who-are-changing-the-world",
				date: "2017-01-24",
				snippet: "...an exclusive group of influencers in business from across the economy and around the globe",
				logo: "/img/press/logos/fastco.png"
			},
			{
				title: "Three New Ways to Baby-Block in the Age of Trump",
				company: "Vice",
				url:
					"https://tonic.vice.com/en_us/article/three-new-ways-to-baby-block-in-the-age-of-trump?utm_source=tonictwitterus",
				date: "2017-01-18",
				snippet:
					"There’s also Maven Clinic, which is entirely women-centric and seems designed to cater to the reality of thousands of women who spend hours scrolling through WebMD with questions about their potential yeast infections.",
				logo: "/img/press/logos/vice.png"
			},
			{
				title: "Now You Can Get Birth Control Through These Apps ",
				company: "Buzzfeed",
				url:
					"https://www.buzzfeed.com/stephaniemlee/these-apps-deliver-birth-control-to-your-door?utm_term=.as6M4KWdk#.rlPYv2qK0",
				date: "2017-01-11",
				snippet:
					"On Maven’s app, which lets patients video-conference and message with nurse practitioners, birth control pills are, perhaps unsurprisingly, the most requested prescription",
				logo: "/img/press/logos/buzzfeed.png"
			},
			{
				title: "The 21-Hottest Women-Founded Startups to Watch in 2017",
				company: "Business Insider",
				url: "http://www.businessinsider.com/top-female-founded-startups-to-watch-2017-1",
				date: "2017-01-08",
				snippet:
					"Ryder noticed that her friends were getting pregnant and receiving a lot of misinformation or having trouble finding the right doctor.",
				logo: "/img/press/logos/bi.png"
			},
			{
				title: "Here’s What Healthcare For Women in the Workplace Could Look Like in 2017",
				company: "Forbes",
				url:
					"https://www.forbes.com/sites/break-the-future/2017/01/03/heres-what-healthcare-for-women-in-the-workplace-could-look-like-in-2017/#1a20481812e2",
				date: "2017-01-03",
				snippet:
					"Business leaders have already started a shift toward much more robust support of women in the workplace, not out of goodwill but out of consideration for their bottom line.",
				logo: "/img/press/logos/forbes.png"
			},
			{
				title: "Top 10 Innovations That Made Women’s Lives Better in 2016",
				company: "Fast Company",
				url:
					"https://www.fastcompany.com/3066036/startup-report/the-top-10-innovations-that-made-womens-lives-2016-better-in",
				date: "2016-12-15",
				snippet:
					"The company works with hundreds of providers that sit inside and outside of the traditional medical system",
				logo: "/img/press/logos/fastco.png"
			},
			{
				title: "Why Trump and Congress should keep women in mind when retooling Obamacare",
				company: "CNBC",
				url:
					"http://www.cnbc.com/2016/12/10/why-trump-and-congress-should-keep-women-in-mind-when-retooling-obamacare.html",
				date: "2016-12-10",
				snippet: "Right now our health-care system is really inconvenient, and there are gaps in women’s care",
				logo: "/img/press/logos/cnbc.png"
			},
			{
				title: "100 of the most exciting startups in New York City ",
				company: "Business Insider",
				url:
					"http://www.businessinsider.com/100-of-the-most-exciting-startups-in-new-york-city-2016-12?op=0#/#maven-the-first-digital-clinic-for-women-55",
				date: "2016-12-08",
				snippet: "Maven makes it easier for women to get immediate, professional care, from someone they trust.",
				logo: "/img/press/logos/bi.png"
			},
			{
				title: "Maven is now offering free birth control post-election",
				company: "Fast Company",
				url: "https://news.fastcompany.com/maven-is-now-offering-free-birth-control-post-election-4025336",
				date: "2016-11-17",
				snippet:
					"...the company made this step in response to user concerns that an Affordable Care Act mandate that guarantees converage for contraception without any co-payment or coinsurance would be repealed.",
				logo: "/img/press/logos/fastco.png"
			},
			{
				title: "Maven offers free birth control prescriptions via digital doctors",
				company: "Engadget",
				url: "https://www.engadget.com/2016/11/16/birth-control-iud-maven-free-digital-doctor-appointment/",
				date: "2016-11-16",
				snippet:
					"At Maven, one thing we believe will never change: getting birth control easily and affordably is a social imperative.",
				logo: "/img/press/logos/engadget.png"
			},
			{
				title: "How Can I Afford Mental Health Care?",
				company: "The Cut",
				url: "https://www.thecut.com/2016/11/how-to-afford-healthcare-for-mental-illness.html",
				date: "2016-11-11",
				snippet:
					"Finding a provider who makes you feel comfortable and has the specialty you need shouldn’t be restricted by your health insurance or location",
				logo: "/img/press/logos/thecut.png"
			},
			{
				title: "6 Websites and Apps You Can Use to Get Birth Control",
				company: "Glamour",
				url: "http://www.glamour.com/story/websites-apps-birth-control",
				date: "2016-06-23",
				snippet:
					"Maven also does a video consultation about anything health-related from mental health to reproductive health",
				logo: "/img/press/logos/glamour.png"
			},
			{
				title: "The On-Demand Economy Hits the Reset Button",
				company: "Fast Company",
				url: "https://www.fastcompany.com/3060525/the-on-demand-economy-hits-the-reset-button",
				date: "2016-06-20",
				snippet:
					"We’re delivering care in a way that it should be delivered, which is in a subscription, peace-of-mind, premium service.",
				logo: "/img/press/logos/fastco.png"
			},
			{
				title: "Birth Control via App Finds Footing Under Political Radar",
				company: "The New York Times",
				url: "https://www.nytimes.com/2016/06/20/health/birth-control-options-websites.html",
				date: "2016-06-19",
				snippet: "A quiet shift is taking place in how women obtain birth control.",
				logo: "/img/press/logos/nyt.png"
			},
			{
				title: "Which Birth Control App or Website Should You Use?",
				company: "The New York Times",
				url: "https://www.nytimes.com/interactive/2016/health/birth-control-options-apps.html?_r=0",
				date: "2016-06-19",
				snippet:
					"A growing number of websites and digital apps enable women to obtain birth control without visiting a doctor.",
				logo: "/img/press/logos/nyt.png"
			},
			{
				title: "The New Generation of Pregnancy Websites and Apps You Need to Know About",
				company: "Washington Post",
				url:
					"https://www.washingtonpost.com/news/parenting/wp/2016/04/21/the-new-generation-of-pregnancy-websites-and-apps-you-need-to-know-about/",
				date: "2016-04-21",
				snippet:
					"Google the weather, not your symptoms is Maven’s tagline, and this complete women’s tele-health app is trying to make thta easy.",
				logo: "/img/press/logos/wapo.png"
			},
			{
				title: "Like a Boss: Meet the Winners of Glamour’s Annual Starter’s Project ",
				company: "Glamour",
				url: "http://www.glamour.com/story/glamour-starters-project-2016-winners",
				date: "2016-04-01",
				snippet: "The doubters just made me more juiced than ever to prove them wrong.",
				logo: "/img/press/logos/glamour.png"
			},
			{
				title: "My Computer, the Therapist: Is Digital Counseling the Next Big Online Frontier?",
				company: "Vogue",
				url: "http://www.vogue.com/article/digital-counseling-therapy-online-app",
				date: "2016-03-01",
				snippet: "Maven, which puts an Uber spin on mental health",
				logo: "/img/press/logos/vogue.png"
			},
			{
				title: "Have All the Sex You Want, Because you Can Now Get Birth Control Through an App",
				company: "Maxim",
				url: "https://www.maxim.com/maxim-man/get-birth-control-through-app-2016-1",
				date: "2016-01-18",
				snippet: "...birth control is now available for near-instant delivery through apps on your smartphone",
				logo: "/img/press/logos/maxim.png"
			},
			{
				title: "Now You Can Get Birth Control Through These Apps ",
				company: "Buzzfeed",
				url:
					"https://www.buzzfeed.com/stephaniemlee/these-apps-deliver-birth-control-to-your-door?utm_term=.yuo6oeJXqP#.axg6WxX5b7",
				date: "2016-01-11",
				snippet: "Providers recommend a medication on the spot and order it to be sent to a pharmacy near the patient.",
				logo: "/img/press/logos/buzzfeed.png"
			},
			{
				title: "5 cool, innovative wellness apps that launched in 2015",
				company: "Well and Good",
				url: "https://www.wellandgood.com/good-advice/best-health-wellness-apps/slide/3/",
				date: "2015-12-27",
				snippet:
					"So if you feel a UTI coming on on a Sunday when your doctor is out of office or are a new mom that needs some on-the-fly lactation advice, you can solve your issue quickly",
				logo: "/img/press/logos/wellandgood.png"
			},
			{
				title: "Check Out the App That Lets You Visit the Doctor’s Office From Your iPhone",
				company: "Teen Vogue",
				url: "http://www.teenvogue.com/story/maven-health-services-app-college-students",
				date: "2015-12-09",
				snippet:
					"...it’s a great resource to turn to when you have a question, and the Internet is telling you, it’s probably cancer.",
				logo: "/img/press/logos/teenvogue.png"
			},
			{
				title: "Telehealth: Patient care via smartphone",
				company: "Los Angeles Times",
				url: "http://www.latimes.com/health/la-he-heal-side-20151107-story.html",
				date: "2015-11-07",
				snippet:
					"Prices range from $18 for a 10-minute consultation with a nurse practitioner to $70 for a 40-minute chat with a mental health professional. Patients fill in a basic medical history online before speaking with the practitioner and then receive follow-up documentation afterward recounting what occurred during the conversation.",
				logo: "/img/press/logos/latimes.png"
			},
			{
				title: "Why (Almost) Everyone is Embracing the Digital Doctor",
				company: "TIME",
				url: "http://time.com/4092350/why-almost-everyone-is-embracing-the-digital-doctor/",
				date: "2015-10-29",
				snippet:
					"Maven, which launched in April, is one of several new digital platforms that let patients video-chat with doctors and get common prescriptions at any hour of the day, seven days a week.",
				logo: "/img/press/logos/time.png"
			},
			{
				title: "Meet Maven: The Telehealth Pioneer for Women",
				company: "Forbes",
				url: "https://www.forbes.com/sites/alextaub/2015/09/24/maven-the-telehealth-pioneer-for-women/#a33de176f0fa",
				date: "2015-09-24",
				snippet:
					"Maven’s mission is to support the female healthcare consumer navigating our complicated healthcare system.",
				logo: "/img/press/logos/forbes.png"
			},
			{
				title: "10 Healthcare Technology Disruptors to Watch (All Led by Women)",
				company: "Forbes",
				url:
					"https://www.forbes.com/sites/kateharrison/2015/08/13/10-healthcare-technology-disruptors-to-watch-all-led-by-women/2/#1f680ab71a3b",
				date: "2015-08-13",
				snippet:
					"Maven Clinic offers a tele-health platform that creates video appointments with healthcare providers for convenient quality care with a more human experience.",
				logo: "/img/press/logos/forbes.png"
			},
			{
				title: "The Unexpected Rise of the On-Demand Digital Doula",
				company: "Elle",
				url: "http://www.elle.com/life-love/sex-relationships/news/a29024/moms-now-hiring-digital-doulas/",
				date: "2015-06-26",
				snippet:
					"With Maven, new moms don’t need to be schedulers, jugglers, or dressed to impress in order to get some much-needed help.",
				logo: "/img/press/logos/elle.png"
			},
			{
				title: "Today's Travel News and Tips, Women’s Health, By App ",
				company: "The New York Times",
				url: "https://www.nytimes.com/2015/06/04/travel/todays-travel-news-and-tips.html?_r=0",
				date: "2015-06-04",
				snippet:
					"Medical issues can come up on the road, but the new app Maven gives female travelers the chance to deal with them",
				logo: "/img/press/logos/nyt.png"
			},
			{
				title: "An Uber for Doctor Housecalls ",
				company: "The New York Times",
				url: "https://well.blogs.nytimes.com/2015/05/05/an-uber-for-doctor-housecalls/",
				date: "2015-05-05",
				snippet:
					"...Maven focusses specifically on women’s health, including issues related to fertility, pregnancy and postpartum care",
				logo: "/img/press/logos/nyt.png"
			},
			{
				title: "You Can Now See Your Doctor...on Your Phone",
				company: "Marie Claire",
				url: "http://www.marieclaire.com/health-fitness/news/a14327/doctor-appointment-app-maven/",
				date: "2015-05-05",
				snippet:
					"We’ve made it an important point to make sure the ‘human’ element in healthcare is part of the experience.",
				logo: "/img/press/logos/marieclaire.png"
			},
			{
				title: "30 HealthTech Startups with Real Potential to Change the World",
				company: "Alley Watch",
				url: "http://www.alleywatch.com/2015/05/30-healthtech-startups-with-the-potential-to-change-the-world/",
				date: "2015-05-05",
				snippet: "Maven is poised to change everything.",
				logo: "/img/press/logos/alleywatch.png"
			},
			{
				title: "This Women Focused Telemedical NYC Startup Just Raised $2.2 Million",
				company: "Alley Watch",
				url: "http://www.alleywatch.com/2015/04/this-women-focused-telemedical-nyc-startup-just-raised-2-2m/",
				date: "2015-04-24",
				snippet:
					"So this is a tool to make women’s lives a bit easier when it comes to managing health & wellness for themselves and their family",
				logo: "/img/press/logos/alleywatch.png"
			},
			{
				title: "3 Can’t Miss Life Hacks To Try This Week",
				company: "Refinery29",
				url: "http://www.refinery29.com/2015/04/85417/life-lessons-apps",
				date: "2015-04-13",
				snippet:
					"They provide professional feedback on what ails you, and they give you the healthiest thing of all: peace of mind.",
				logo: "/img/press/logos/refinery29.png"
			},
			{
				title: "Why Are These 3 STEM Fields Dominated by Women?",
				company: "Fast Company",
				url: "https://www.fastcompany.com/3044934/strong-female-lead/why-are-these-3-stem-fields-dominated-by-women",
				date: "2015-04-13",
				snippet:
					"That experience helped her design a company that would not only cater to the specific needs of female patients, but also serve as a vehicle to employ and empower female healthcare providers who weren’t physicians.",
				logo: "/img/press/logos/fastco.png"
			},
			{
				title: "Maven Launches the First Telemedicine Platform Made for Women with 2.2 Million in Seed",
				company: "TechCrunch",
				url:
					"https://techcrunch.com/2015/04/09/maven-launches-the-first-telemedicine-platform-made-for-women-with-2-2-million-in-seed/",
				date: "2015-04-09",
				snippet: "I found that what was out their didn’t have specific focuson women’s health.",
				logo: "/img/press/logos/techcrunch.png"
			},
			{
				title: "Your Teledoctor Will See You Now",
				company: "New York Magazine",
				url: "http://nymag.com/next/2015/04/mobile-health-care-app-maven-launches.html",
				date: "2015-04-09",
				snippet:
					"So we wanted to take every type of health-care provider a woman would ever touch, from an OB/GYN to a nutritionist, and give her the ability to access them at any time.",
				logo: "/img/press/logos/nymag.png"
			},
			{
				title: "The Daily Startup: Maven Clinic Launches Women’s Telemedicine Apps",
				company: "The Wall Street Journal",
				url:
					"https://blogs.wsj.com/venturecapital/2015/04/09/the-daily-startup-maven-clinic-launches-womens-telemedicine-apps/",
				date: "2015-04-09",
				snippet: "Maven Clinic is focusing its telemedicine apps on women’s health services...",
				logo: "/img/press/logos/wsj.png"
			},
			{
				title: "Maven wants to turn your smartphone into a women’s health clinic",
				company: "Fortune",
				url: "http://fortune.com/2015/04/09/maven-wants-to-turn-your-smartphone-into-a-womens-health-clinic/",
				date: "2015-04-09",
				snippet:
					"The service...is designed to bridge the gap between non-essential office visits and the typical alternative-Googling for advice online.",
				logo: "/img/press/logos/fortune.png"
			}
		]

		$scope.announcements = [
			{
				title: "Maven Teams Up with UrbanSitter to Offer Healthcare + Childcare On-Demand",
				date: "2018-07-09",
				snippet:
					"Maven members will now receive an exclusive 25% discount on UrbanSitter membership which they can use to find trusted babysitters and nannies in their area",
				url: "https://blog.mavenclinic.com/for-business/maven-teams-up-with-urbansitter"
			},
			{
				title: "Maven and Bumble Partner to Advance Women in the Workforce",
				date: "2018-05-14",
				snippet:
					"Bumble will be offering its employees Maven’s comprehensive family benefits program for personalized pregnancy, postpartum, back-to-work, fertility, and egg freezing support—all on one unified platform",
				url: "https://blog.mavenclinic.com/for-business/maven-and-bumble-partner-to-advance-women-in-the-workforce"
			},
			{
				title: "Maven Founder & CEO, Kate Ryder, Speaks at HLTH Conference in Las Vegas",
				date: "2018-05-08",
				snippet:
					"Our founder and CEO, Katherine Ryder, spoke on a panel about personalized approaches to care on the second day of the HLTH conference",
				url: "https://blog.mavenclinic.com/for-business/maven-hlth-conference-recap"
			},
			{
				title:
					"Maven executive, Michelle Gile, to vie for Innovators Showcase Award during 11th Annual Minnesota Health Action Group Employer Leadership Summit",
				date: "2018-05-03",
				snippet:
					"Maven demonstrated its program, Maven Maternity, to more than 200 Minnesota employers, health care experts, and health care companies who are expected to attend the Minnesota Health Action Group Employee Leadership Summit",
				url: "https://blog.mavenclinic.com/for-business/maven-vies-for-innovators-showcase-award"
			},
			{
				title: "Kate Ryder, CEO & Founder, to speak at Crain's Summit",
				date: "2018-05-02",
				snippet:
					"Maven Founder & CEO Kate Ryder Speaks at Crain's Healthcare Summit on Investing In Digital Health Innovation"
			},
			{
				title: "Maven CEO & Founder, Kate Ryder, featured in May Vogue",
				date: "2018-04-22",
				snippet:
					"Kate Ryder writes about her journey to starting Maven and her experience as a mother in the May edition of Vogue"
			},
			{
				title: "Maven Clinic and Castlight Health Announce New Partnership",
				date: "2018-03-14",
				url:
					"https://blog.mavenclinic.com/for-business/maven-clinic-announces-new-partnership-with-castlight-health-to-offer-comprehensive-parental-support-platform-to-customers"
			},
			{
				title: "Digital Women’s Health Clinic Offers Free Healthcare for International Women’s Day",
				date: "2018-03-14",
				url: "https://blog.mavenclinic.com/for-individuals/international-womens-day"
			},
			{
				title: "Maven Named One of World’s Most Innovative Healthcare Companies by Fast Company",
				date: "2018-02-14",
				url: "https://www.fastcompany.com/company/maven"
			},
			{
				title: "Maven Teams Up With The Children’s Village to Help Homeless Teen Mothers in NYC",
				date: "2018-02-14",
				url:
					"https://blog.mavenclinic.com/for-business/maven-teams-up-with-the-childrens-village-to-help-homeless-teen-mothers-in-nyc"
			},
			{
				title: "Mayor de Blasio Delivers Remarks on Growing New York Tech Sector from Maven’s New York Headquarters",
				date: "2017-09-14",
				url: "https://www.youtube.com/watch?v=72G6eS11ZN0",
				cta: "Watch now"
			},
			{
				title: "Maven CEO on Maven’s $11M Series A to Put the Female Patient in the Driver’s Seat of Healthcare",
				date: "2017-07-14",
				url:
					"https://blog.mavenclinic.com/for-business/maven-raises-11m-series-a-to-put-female-patients-in-the-drivers-seat-of-healthcare"
			}
		]

		$scope.readMorePress = () => {
			$scope.pressPieces = $scope.pressPieces.concat(_getNPosts(12, $scope.parsedPressPieces))
		}

		const _getNPosts = (n, arr) => {
			let posts = []
			const iterator = Math.min(n, arr.length)
			for (var i = 0; i < iterator; i++) {
				posts.push(arr.shift())
			}
			return posts
		}

		const _parsePressData = data => {
			const cutoff = 90
			const parsed = data.map(d => {
				if (d.snippet.length > cutoff) {
					d.snippet = `${d.snippet.substring(0, cutoff - 3)}...`
				}

				return d
			})

			return parsed
		}

		const init = () => {
			$scope.parsedPressPieces = _parsePressData(pressData)
			$scope.pressPieces = _getNPosts(12, $scope.parsedPressPieces)
		}

		init()
	}
])
