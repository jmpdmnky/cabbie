module.exports = {
    NODE_ENV: 'production',
    TASKS_API_URL: 'https://${resource.id:tasks_api}.execute-api.us-east-1.amazonaws.com/${resource.stage:tasks_api}/tasks/',
    LOGIN_URL: 'https://${resource.id:auth_api}.execute-api.us-east-1.amazonaws.com/${resource.stage:auth_api}/auth/login',
    LOGOUT_URL: 'https://${resource.id:auth_api}.execute-api.us-east-1.amazonaws.com/${resource.stage:auth_api}/auth/logout',
    SIGNUP_URL: 'https://${resource.id:auth_api}.execute-api.us-east-1.amazonaws.com/${resource.stage:auth_api}/auth/signup',
    RESEND_VERIFICATION_URL: 'https://${resource.id:auth_api}.execute-api.us-east-1.amazonaws.com/${resource.stage:auth_api}/auth/resendverification/',
    ORGS_API_URL: 'https://${resource.id:tasks_api}.execute-api.us-east-1.amazonaws.com/${resource.stage:tasks_api}/orgs',
    TEAMS_API_URL: 'https://${resource.id:tasks_api}.execute-api.us-east-1.amazonaws.com/${resource.stage:tasks_api}/teams',
    USERS_API_URL: 'https://${resource.id:tasks_api}.execute-api.us-east-1.amazonaws.com/${resource.stage:tasks_api}/users'
};
