/**
 * Neural Atelier NA - Styling Detail Change UI Extension for ComfyUI
 * Provides dynamic 3-level dropdown, API verification, and re-run functionality
 */

import { app } from "../../scripts/app.js";

const NODE_TYPE = "NA_StylingDetailChange";

let garmentsConfig = null;

async function loadGarmentsConfig() {
    if (garmentsConfig !== null) {
        return garmentsConfig;
    }
    
    try {
        const response = await fetch("/neural_atelier/styling/garments_config");
        if (response.ok) {
            garmentsConfig = await response.json();
            return garmentsConfig;
        }
    } catch (e) {
        console.error("Failed to load garments config:", e);
    }
    
    return { garment_types: [] };
}

function findGarmentType(config, value) {
    return config.garment_types?.find(gt => gt.value === value);
}

function findCategory(garmentType, value) {
    return garmentType?.categories?.find(cat => cat.value === value);
}

function getCategoriesForGarment(config, garmentTypeValue) {
    const gt = findGarmentType(config, garmentTypeValue);
    if (!gt || !gt.categories) return [];
    return gt.categories.map(cat => cat.value);
}

function getOptionsForCategory(config, garmentTypeValue, categoryValue) {
    const gt = findGarmentType(config, garmentTypeValue);
    if (!gt) return [];
    const cat = findCategory(gt, categoryValue);
    if (!cat || !cat.options) return [];
    return cat.options.map(opt => opt.value);
}

function getDefaultTemplate(config, garmentTypeValue, categoryValue) {
    const gt = findGarmentType(config, garmentTypeValue);
    if (!gt) return "";
    const cat = findCategory(gt, categoryValue);
    return cat?.default_template || "";
}

app.registerExtension({
    name: "NeuralAtelier.Styling",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== NODE_TYPE) {
            return;
        }
        
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = async function() {
            const result = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            
            const config = await loadGarmentsConfig();
            
            const garmentTypeWidget = this.widgets?.find(w => w.name === "garment_type");
            const detailCategoryWidget = this.widgets?.find(w => w.name === "detail_category");
            const detailOptionWidget = this.widgets?.find(w => w.name === "detail_option");
            const descriptionWidget = this.widgets?.find(w => w.name === "description");
            const apiKeyWidget = this.widgets?.find(w => w.name === "gemini_api_key");
            const statusWidget = this.widgets?.find(w => w.name === "api_key_status");
            const rerunNonceWidget = this.widgets?.find(w => w.name === "rerun_nonce");
            
            const updateCategories = () => {
                if (!garmentTypeWidget || !detailCategoryWidget) return;
                
                const garmentType = garmentTypeWidget.value;
                const categories = getCategoriesForGarment(config, garmentType);
                
                if (categories.length > 0) {
                    detailCategoryWidget.options = { values: categories };
                    if (!categories.includes(detailCategoryWidget.value)) {
                        detailCategoryWidget.value = categories[0];
                    }
                }
                
                updateOptions();
            };
            
            const updateOptions = () => {
                if (!garmentTypeWidget || !detailCategoryWidget || !detailOptionWidget) return;
                
                const garmentType = garmentTypeWidget.value;
                const category = detailCategoryWidget.value;
                const options = getOptionsForCategory(config, garmentType, category);
                
                if (options.length > 0) {
                    detailOptionWidget.options = { values: options };
                    if (!options.includes(detailOptionWidget.value)) {
                        detailOptionWidget.value = options[0];
                    }
                }
                
                updateDescriptionTemplate();
            };
            
            const updateDescriptionTemplate = () => {
                if (!garmentTypeWidget || !detailCategoryWidget || !detailOptionWidget || !descriptionWidget) return;
                
                const garmentType = garmentTypeWidget.value;
                const category = detailCategoryWidget.value;
                const option = detailOptionWidget.value;
                
                const template = getDefaultTemplate(config, garmentType, category);
                if (template) {
                    descriptionWidget.value = template.replace("{OPTION}", option);
                }
            };
            
            if (garmentTypeWidget) {
                const originalCallback = garmentTypeWidget.callback;
                garmentTypeWidget.callback = function(value) {
                    if (originalCallback) originalCallback.call(this, value);
                    updateCategories();
                };
            }
            
            if (detailCategoryWidget) {
                const originalCallback = detailCategoryWidget.callback;
                detailCategoryWidget.callback = function(value) {
                    if (originalCallback) originalCallback.call(this, value);
                    updateOptions();
                };
            }
            
            if (detailOptionWidget) {
                const originalCallback = detailOptionWidget.callback;
                detailOptionWidget.callback = function(value) {
                    if (originalCallback) originalCallback.call(this, value);
                    updateDescriptionTemplate();
                };
            }
            
            if (apiKeyWidget && statusWidget) {
                const verifyBtn = this.addWidget("button", "Verify API Key", null, () => {
                    const apiKey = apiKeyWidget.value;
                    if (!apiKey) {
                        statusWidget.value = "Missing API Key";
                        return;
                    }
                    
                    statusWidget.value = "Verifying...";
                    
                    fetch("/neural_atelier/verify_api", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ api_key: apiKey })
                    })
                        .then(r => r.json())
                        .then(data => {
                            statusWidget.value = data.message;
                        })
                        .catch(e => {
                            statusWidget.value = "Network Error";
                            console.error(e);
                        });
                });
                verifyBtn.serialize = false;
            }
            
            if (rerunNonceWidget) {
                const rerunBtn = this.addWidget("button", "Re-run from here", null, () => {
                    rerunNonceWidget.value = (rerunNonceWidget.value || 0) + 1;
                    app.queuePrompt(0, 1);
                });
                rerunBtn.serialize = false;
            }
            
            return result;
        };
    }
});
