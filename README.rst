So this project has largely become focused on using a GIST backend. The CLI stuff still exists, but it's not something I use. Should probably make a new project but, well, I'm a bum.

INSTALL
=======

Install normally. However, you will need to manually move /bin/ipycli into your $PATH. 

Example Usage:
ipycli --pylab=inline --port=8888 --ip='*' --no-browser --github-user=gh_user --github-pw=gh_password

Q&A
==========

*Does every gist show up as a notebook?*

No. Conceptually, a GIST is only a GIST Notebook if it has a '#notebook' in its description. Any other hashtagged words will be processed as a tag. So a GIST with the description "Hello World #notebook #test" will show under the tag #test. 

*What happens when you delete a gist from the ipycli? *

Deleting a GIST from ipycli will merely add the #inactive tag which tells ipycli to ignore it on the main menu. You can view deleted gists from the Show All tab. 

*Can I create a new tag from ipycli?* 

Currently no. In order to seed a new tag, you need to create a new GIST from gist.github.com with the appropiate tags. Remember, a GIST requires at least one file to be created, DO NOT make it an .ipynb. ipycli will automatically create a proper bare .ipynb if the GIST does not have one.

*I don't get it, how do I create a tag.*

1) Go to gist.github.com and create a new gist. If the tag you want is #quant, then something like "sp500 data #notebook #quant". Create a dummy file called README with any text. 
2) Open up the ipycli window and refresh. You should now see that notebook. 
3) Click on the notebook. It will now create a new Untitled.ipynb and then open up a notebook window. You can verify the creation on gist.github.com

*Does renaming work?*

Yes. 

*What is this transient tag?*

#transient is a system tag that is for throwaway notebooks. The #transient section on the main page will only show the most recent 5 notebooks. The Transient tab will show all #transient notebooks. 

*Why is my keyboard input all funky?*

You are likely in vim-mode. Im try to change keyboard input back to default when committing an update, however sometimes I forget and commit it as vim. To fix this, comment out the following line in static/js/notebook.js

        this.keyMap = 'vim';

*Does this thing autosave?*

Yes. It will save every 3 minutes. It has some logic in there to only save during an idle window. Since a GIST is auto-reversioning I want to be liberal with the autosaving. However, since autosaving isn't instantaneous, being too liberal will delay things like auto-complete and executing cells. 

*Why do I sometimes get lag with autocomplete and cell execution?*

I tried to strike a good balance between autosaving and IPython shell response. The problem is that they share the same pipe and saving to github will block the other calls until it is done. I'm not entirely sure how to fix this in a complete way.

*Why are there two create notebook buttons?*

One is for public GISTs and the other is for private. 

SCREENSHOT
==========

.. image:: https://www.evernote.com/shard/s9/sh/d1ae412a-916e-4d12-9d28-56a34f577744/d7f51fc3c792132303026c39767c2c28/res/78f58df1-a319-45c7-8dc9-11bc24892c12/skitch.png

Fake gist example:
https://gist.github.com/fakedale
