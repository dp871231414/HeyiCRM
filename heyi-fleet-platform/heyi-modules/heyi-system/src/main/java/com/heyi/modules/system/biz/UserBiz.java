package com.heyi.modules.system.biz;

import com.heyi.modules.system.manager.UserManager;
import com.heyi.modules.system.service.UserService;
import com.heyi.publics.common.annotation.DynamicUserFields;
import com.heyi.publics.common.exception.BizException;
import com.heyi.publics.common.util.CopyUtil;
import com.heyi.publics.common.util.IdUtil;
import com.heyi.publics.entity.User;
import com.heyi.publics.entity.form.UserSaveForm;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class UserBiz {

    private final UserService userService;
    private final UserManager userManager;
    private final BCryptPasswordEncoder passwordEncoder;

    @DynamicUserFields
    @Transactional(rollbackFor = Exception.class)
    public User create(UserSaveForm form) {
        if (userManager.existsAccount(form.getAccount(), null)) {
            throw new BizException("账号已存在");
        }
        User po = CopyUtil.copy(form, User::new);
        po.setId(IdUtil.nextId());
        po.setPasswordHash(passwordEncoder.encode(form.getPassword() == null ? "123456" : form.getPassword()));
        po.setStatus(form.getStatus() == null ? "active" : form.getStatus());
        po.setDeletedAt(0L);
        userService.save(po);
        return po;
    }

    @DynamicUserFields
    @Transactional(rollbackFor = Exception.class)
    public User update(Long id, UserSaveForm form) {
        User po = userService.getById(id);
        if (po == null) {
            throw new BizException("账号不存在");
        }
        if (form.getName() != null) {
            po.setName(form.getName());
        }
        if (form.getDeptId() != null) {
            po.setDeptId(form.getDeptId());
        }
        if (form.getRoleId() != null) {
            po.setRoleId(form.getRoleId());
        }
        if (form.getScope() != null) {
            po.setScope(form.getScope());
        }
        if (form.getStatus() != null) {
            po.setStatus(form.getStatus());
        }
        if (form.getPassword() != null && !form.getPassword().isEmpty()) {
            po.setPasswordHash(passwordEncoder.encode(form.getPassword()));
        }
        userService.updateById(po);
        return po;
    }

    @Transactional(rollbackFor = Exception.class)
    public void remove(Long id) {
        User po = userService.getById(id);
        if (po == null) {
            throw new BizException("账号不存在");
        }
        po.setDeletedAt(System.currentTimeMillis());
        userService.updateById(po);
    }

    /**
     * 登录校验：账号不存在与被停用分别提示；密码错误统一提示"账号或密码错误"（不泄露账号是否存在）。
     */
    public User login(String account, String password) {
        User user = userManager.selectByAccount(account);
        if (user == null || !passwordEncoder.matches(password == null ? "" : password, user.getPasswordHash())) {
            throw new BizException("账号或密码错误");
        }
        if ("disabled".equals(user.getStatus())) {
            throw new BizException("账号已停用，请联系管理员");
        }
        return user;
    }
}
