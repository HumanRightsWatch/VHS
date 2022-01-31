# Administration guide

Three important information are specified at the deployment time:

* the URL to access VHS
* the URL to access VHS administration panel
* the password of default administrator account

You should ask the person who deployed VHS the following pieces of information:

* `DJANGO_ADMIN_URL` corresponding to the URL to access VHS administration panel
* `ADMIN_PASSWORD` corresponding to the password of default administrator account

## 2 types of account
VHS manages 2 different types of account:

* local account: account that only exists on VHS
* external accounts: account belonging to your organization

The local account is useful in two cases:

* grant administration permissions to a set of external accounts
* re-configure the SSO

## Grant permissions
In the administration panel, you should create a *Group* named `admin`. Any account belonging to this group will see:

* the collections of everybody
* all the different metadata regarding downloaded files

To add a person into the `admin` group, the person has to first log in with their organization's account. This way, you will be able to add the account to the group. To do so, in the administration pane, browse *Users*, click on the user you want to edit, click on `admin` in the *Groups* section, click on `>` to add this group to the user and finally click on "Save". 

## Super user
In addition, VHS also has a concept of *super user* who has access to the administration panel. To grant this access to an account, browse *Users*, click on the user you want to edit, check the boxes *Staff* and *Super user*, click on *Save*.



