package com.heyi.modules.system.controller;

import cn.dev33.satoken.stp.StpUtil;
import com.heyi.modules.system.biz.UserBiz;
import com.heyi.publics.common.result.R;
import com.heyi.publics.entity.User;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {

    private final UserBiz userBiz;

    @PostMapping("/login")
    public R<Map<String, Object>> login(@RequestParam String account, @RequestParam String password) {
        User user = userBiz.login(account, password);
        StpUtil.login(user.getAccount());
        Map<String, Object> data = new HashMap<>();
        data.put("token", StpUtil.getTokenValue());
        data.put("name", user.getName());
        data.put("account", user.getAccount());
        return R.ok(data);
    }

    @PostMapping("/logout")
    public R<Boolean> logout() {
        StpUtil.logout();
        return R.ok(true);
    }

    @PostMapping("/is-login")
    public R<Boolean> isLogin() {
        return R.ok(StpUtil.isLogin());
    }
}
