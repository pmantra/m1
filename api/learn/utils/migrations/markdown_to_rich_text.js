// This script is meant to be run locally after installing node and
// the Contentful rich text from markdown package.
// Not meant to be run on prod.
// Takes two arguments: the filename to read from and the filename to write to.
const fs = require('fs');
const { richTextFromMarkdown } = require('@contentful/rich-text-from-markdown');

const process_markdown = async function() {
    const args = process.argv.slice(2)
    const data = fs.readFileSync(args[0], 'utf8');
    let resources = JSON.parse(data);
    let resources_with_asterisks_slugs = new Set();
    for (let k in resources) {
        let md = resources[k]["fields"]["richText"]["en-US"];
        let richText = await richTextFromMarkdown(md);
        // Asterisks in article bodies are rare; if one shows up, it's more likely
        // that it's markdown that wasn't transformed correctly
        if (JSON.stringify(richText).includes("*")) {
            resources_with_asterisks_slugs.add(resources[k]["fields"]["slug"]["en-US"]);
        }
        resources[k]["fields"]["richText"]["en-US"] = richText;

        accordions = resources[k]["embedded_entries"]["accordions"];
        if (accordions) {
            for (let accordion_k in accordions) {
                let items = []
                for (let item of accordions[accordion_k]["items"]) {
                    let itemRichText = await richTextFromMarkdown(item["rich_text"])
                    if (JSON.stringify(itemRichText).includes("*")) {
                        resources_with_asterisks_slugs.add(resources[k]["fields"]["slug"]["en-US"]);
                    }
                    item["rich_text"] = itemRichText;
                    items.push(item);
                }
                resources[k]["embedded_entries"]["accordions"][accordion_k]["items"] = items;
            }
        }

        callouts = resources[k]["embedded_entries"]["callouts"];
        if (callouts) {
            for (let [i, callout] of callouts.entries()) {
                let calloutRichText = await richTextFromMarkdown(callout["body"])
                if (JSON.stringify(calloutRichText).includes("*")) {
                    resources_with_asterisks_slugs.add(resources[k]["fields"]["slug"]["en-US"]);
                }
                resources[k]["embedded_entries"]["callouts"][i]["body"] = calloutRichText;
            }
        }

        embeddedImages = resources[k]["embedded_entries"]["embedded_images"];
        if (embeddedImages) {
            for (let [i, embeddedImage] of embeddedImages.entries()) {
                if (embeddedImage["caption"]) {
                    let captionRichText = await richTextFromMarkdown(embeddedImage["caption"])
                    if (JSON.stringify(captionRichText).includes("*")) {
                        resources_with_asterisks_slugs.add(resources[k]["fields"]["slug"]["en-US"]);
                    }
                    resources[k]["embedded_entries"]["embedded_images"][i]["caption"] = captionRichText;
                }
            }
        }
    }

    if (resources_with_asterisks_slugs.size > 0) {
        console.log("Resources with asterisks, which may be markdown residue; check\n---");
        for (let slug of resources_with_asterisks_slugs) {
            console.log(slug);
        }
    }

    fs.writeFileSync(args[1], JSON.stringify(resources), 'utf8');
}

process_markdown();
