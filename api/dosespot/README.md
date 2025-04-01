# Dosespot 💉

[Dosespot](https://www.dosespot.com/) is a third party service which allows providers to write e-prescriptions for our members. 

Providers sign into Dosespot via Single Sign On, using their Maven identity and a pair of Dosespot keys which must be set manually for them via the admin portal. 

We send providers to the third party interface to write prescriptions, but also pull related notifications into our own interface via their api. 

We handle users picking their pharmacy via our own interface and Dosespot's api. Code calling the Dosespot api is in `api/utils/dosespot.py`.

```
Note: When testing the DoseSpot API on the staging site, only certain pharmacies will accept prescriptions without an error.
```

### When Dosespot Fails
Visit the Salesforce support link titled *Dosespot Salesforce* in the 1password dev vault. 
Additionally, if the key is needed it can be found in the dev vault as well under the title *Dosespot Global Clinic*.

### Further Reading
Check out the [Notion](https://www.notion.so/mavenclinic/DoseSpot-8a1f57d583b449e78ed327734f616598) page for more info!
