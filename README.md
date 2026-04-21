## 1. Add font to website
- Customer give us four font files:
```shell
SVN-NeueHaasGroteskDisplay-Regular.ttf
SVN-NeueHaasGroteskDisplay-Medium.ttf
SVN-DentonCondensed-ThinItalic.ttf
SVN-DentonCondensed-LightItalic.ttf
```
But the italic is different font with regular font, and font-weight is 200-300 
In this case we need to change CSS to make effection
```shell
b, strong {
    font-weight: 500;
}
em {
  font-family: 'DentonCondensed', serif;
  font-style: italic;
  font-weight: 200;
}
em strong,
strong em,
em b,
b em{
  font-family: 'DentonCondensed', serif;
  font-style: italic;
  font-weight: 300;
}
```
And in the UI: to use bold - italic: we must click bold then italic (when click italic, the bold is turn of, but it still works, maybe because SVN-DentonCondensed-LightItalic.ttf is only has font-weight: 300)

## 2. Add a new snippet
- When we add new snippets code, then use UI builder to drag and drop that snippet into page.
- Now we change snippets code - Upgrade module -> Maybe we will get some error like:
```shell
Element '<t name="Products with Intro" t-name="luxboat.s_products_with_intro">' cannot be located in parent view
```
It maybes because of the exists snippets on the page
- Before change code, we should delete the snippet on the page
- Or import the new DB that don't have the snippet on page

## 3. Add dynamic template
- Inherit blog.post to add new image field: snippet_image_1920
- Add new template for product and blog.post
- Add a container, that allow we drag & drop other snippet and we will have the Header. 


## 4. It is very simple to add filter option to dynamic snippet
- We just create a xml file and tell Odoo what we want.(domain...)
- How about if we want to filter by category (dynamic field EX: blog_post.category)???