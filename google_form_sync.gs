const FORM_ID = '1chZ8uChgTDFICJ6ZBMlT_NcfI2J7eZkMG89JBCg862g';
const WEBHOOK_URL = 'https://referral-tracker-wf1e.onrender.com/webhooks/google-form';

function sendResponse_(response) {
  const secret = PropertiesService.getScriptProperties().getProperty('FORM_WEBHOOK_SECRET');
  if (!secret || secret.length < 32) throw new Error('Set the private FORM_WEBHOOK_SECRET script property first.');
  const email = response.getRespondentEmail();
  if (!email) throw new Error('Verified respondent email is missing.');
  const body = JSON.stringify({formId: FORM_ID, email: email, responseId: response.getId()});
  const signature = Utilities.computeHmacSha256Signature(body, secret, Utilities.Charset.UTF_8).map(b => ('0' + ((b + 256) % 256).toString(16)).slice(-2)).join('');
  const result = UrlFetchApp.fetch(WEBHOOK_URL, {method: 'post', contentType: 'application/json', payload: body, headers: {'X-Form-Signature': signature}, muteHttpExceptions: true});
  if (result.getResponseCode() !== 200) throw new Error('Tracker returned HTTP ' + result.getResponseCode() + '. No response data or secret is logged.');
}

function onReferralFormSubmit(e) {
  if (!e || !e.response || e.source.getId() !== FORM_ID) throw new Error('Use a form-submit trigger on the configured form.');
  sendResponse_(e.response);
}

function syncResponses() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    const props = PropertiesService.getScriptProperties();
    const responses = FormApp.openById(FORM_ID).getResponses();
    let cursor = Number(props.getProperty('SYNC_CURSOR') || 0);
    if (!Number.isFinite(cursor) || cursor < 0 || cursor >= responses.length) cursor = 0;
    const end = Math.min(cursor + 50, responses.length);
    for (let i = cursor; i < end; i++) {
      sendResponse_(responses[i]);
      props.setProperty('SYNC_CURSOR', String(i + 1));
    }
    if (end >= responses.length) props.setProperty('SYNC_CURSOR', '0');
  } finally { lock.releaseLock(); }
}

function installReferralSync() {
  const form = FormApp.openById(FORM_ID);
  if (!form.collectsEmail()) throw new Error('Keep verified email collection enabled.');
  const handlers = ScriptApp.getProjectTriggers().map(t => t.getHandlerFunction());
  if (!handlers.includes('onReferralFormSubmit')) ScriptApp.newTrigger('onReferralFormSubmit').forForm(form).onFormSubmit().create();
  if (!handlers.includes('syncResponses')) ScriptApp.newTrigger('syncResponses').timeBased().everyHours(1).create();
}
