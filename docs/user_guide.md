# User Guide

## Introduction

### Scope

This guide will walk through some uses of the UI interface relevant once the
application is built; it does not  cover installation/building, though. Information
about installation is found in [the main repository README.md
file](../README.md).

### Application design intention

This application was designed with the intention to support discovery of NIH
and EU grant patterns.  When installed, the period of time over which the data
from the two sources will be drawn is synced and the data is downloaded
and installed locally as to not require additional "on-line" API calls to the original
data sources, which request such calls be limitted; a side benefit of this
restriction is that the tool
works "off-line", a.k.a. completely on your machine; however there is a cost
--- the data is stored on your machine and therefore takes up storage space.

For the examples in this user guide, the time period was 2015 to October
8, 2026.  This resulted in roung 890 k NIH grants and 90 k EU grants within the
database, which ended up being a little less than 5 GB on my machine.

The primary goal of this effort was to expose the abstracts from both data
sources to "full-text"
searches.  Full text has a technical meaning that is much closer to how most
people thinking about searching for textual information from large blocks of text.
How this was technically achieved is secondary; the fact is
that the main full-text search capability is implemented in the app.
More details of how to use
this capability are available in the UI and will be demonstrated below.

## Using the application

### Landing page and basic search

When you got to http://localhost:3000 via the browser once the app has been started, you should see the following (without the colored circles, which are for orientation):
<img src="images/landing_page.png" />
The three colored circles are for orientation and indicate the following:
- <font color="red">Red</font>: This is the main search input field that is used to write the full-text query against the data base's abstracts.
- <font color="green">Green</font>: This is a drop down guide showing an example of how to write a meaningful query (with boolean logic and wildcard examples).
- <font color="purple">Purple</font>: This is a drop down menu that provides access to helpful functionality that will be described in detail in [a later section](#collections-menu)

When you type in a query and click on the search button, the app is designed to retrieve and display results; I did a query for abstracts containing the word "climate", and the page now looked (without the colored circles for orientation) like:
<img src="images/climate_results.png" />
Here, notice that 100 of 2000 results (specified within the red circle) are displayed although you only see the first few.  Scrolling will show more until you get to the hundredth result, at which point you will see something like:
