module.exports = {
    NODE_ENV: 'production',
    TASKS_API_URL: 'https://${resource.id:tasks_api}.execute-api.us-east-1.amazonaws.com/${resource.stage:tasks_api}/lambda-test/',
    LOGIN_URL: 'https://${resource.id:tasks_api}.execute-api.us-east-1.amazonaws.com/${resource.stage:tasks_api}/auth/login',
    LOGOUT_URL: 'https://${resource.id:tasks_api}.execute-api.us-east-1.amazonaws.com/${resource.stage:tasks_api}/auth/logout',
    SIGNUP_URL: 'https://${resource.id:tasks_api}.execute-api.us-east-1.amazonaws.com/${resource.stage:tasks_api}/auth/signup',
    RESEND_VERIFICATION_URL: 'https://${resource.id:tasks_api}.execute-api.us-east-1.amazonaws.com/${resource.stage:tasks_api}/auth/resendverification/'
};
