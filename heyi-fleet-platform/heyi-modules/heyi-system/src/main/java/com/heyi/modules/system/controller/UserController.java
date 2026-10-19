package com.heyi.modules.system.controller;

import com.heyi.modules.system.biz.UserBiz;
import com.heyi.modules.system.service.UserService;
import com.heyi.publics.common.base.SuperController;
import com.heyi.publics.common.result.R;
import com.heyi.publics.entity.User;
import com.heyi.publics.entity.form.UserSaveForm;
import com.heyi.publics.entity.vo.UserVO;
import com.heyi.publics.common.util.CopyUtil;
import lombok.RequiredArgsConstructor;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController extends SuperController<UserService, User> {

    private final UserService userService;
    private final UserBiz userBiz;

    @Override
    protected UserService service() {
        return userService;
    }

    /** 列表不返回 passwordHash */
    @GetMapping("/vo-list")
    public R<List<UserVO>> voList() {
        return R.ok(CopyUtil.copyList(userService.list(notDeleted()), UserVO::new));
    }

    @PostMapping("/save")
    public R<User> save(@RequestBody @Validated UserSaveForm form) {
        return R.ok(userBiz.create(form));
    }

    @PostMapping("/update")
    public R<User> update(@RequestParam Long id, @RequestBody @Validated UserSaveForm form) {
        return R.ok(userBiz.update(id, form));
    }

    @PostMapping("/delete")
    public R<Boolean> delete(@RequestParam Long id) {
        userBiz.remove(id);
        return R.ok(true);
    }
}
