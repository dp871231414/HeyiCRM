package com.heyi.modules.system.service.impl;

import com.heyi.modules.system.mapper.UserMapper;
import com.heyi.modules.system.service.UserService;
import com.heyi.publics.common.base.SuperServiceImpl;
import com.heyi.publics.entity.User;
import org.springframework.stereotype.Service;

@Service
public class UserServiceImpl extends SuperServiceImpl<UserMapper, User> implements UserService {
}
