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
<br/>
<img src="images/landing_page.png" />
The three colored circles are for orientation and indicate the following:
- <font color="red">Red</font>: This is the main search input field that is used to write the full-text query against the data base's abstracts.
- <font color="green">Green</font>: This is a drop down guide showing an example of how to write a meaningful query (with boolean logic and wildcard examples).
- <font color="purple">Purple</font>: This is a drop down menu that provides access to helpful functionality that will be described in detail in [a later section](#collections)

When you type in a query and click on the search button, the app is designed to retrieve and display results; I did a query for abstracts containing the word "climate", and the page now looked (without the colored circles for orientation) like:
<br/>
<img src="images/climate_results.png" />
Here, notice that 100 of 2000 results (specified within the red circle) are displayed although you only see the first few.  Scrolling will show more until you get to the hundredth result, at which point you will see something like:
<br/>
<img src="images/load_more.png" />
Pushing the "Load more" button (in the red circle in this last image) will load another 100 results provided that many remain.

Also notice that the purple circle in the results image contains the third result.  Clicking on this result opens a "Details Panel" on the right, which looks like:
<br/>
<img src="images/details_page.png" /> 
In this image, the purple  circle is still around the 3rd result, and the red circle is around much of the Details Panel.  Also note the small "x" to the left of the title of the Details Panel; clicking this "x" should close the panel.

The green circle in the results image is around text that says filter.  Clicking filter will open a panel on the left hand side that looks like this:
<br/>
<img src="images/filter_interface.png" />
Here, the red circle indicates a button one can choose to filter the results to show just "NIH" results; other fields in this menu are hopefully self-explanatory.  Once the filter interface is filled, you need to push the "Apply" button (in the green circle in this last figure) in order to actually apply the filter.  I did this with just the NIH filter, and you can see the result below:
<br/>
<img src="images/NIH_filter.png" />
Here, Filter has become Filter (1) --- this is because I used 1 filter.  Also, you can see that we are now showing 100 of only 398 results, and the records all have the "NIH" badge (which can be seen in within the green circle within this last figure.)

### Collections

The collections infrastructure has been implemented.  It was designed to allow the user to create local "collections" of flagged results.  However, I do not have the time to walk through all of the functionality and will fill these section in sometime in the near future.